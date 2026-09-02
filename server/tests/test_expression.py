"""스냅샷 판독 테스트.

Gemini는 부르지 않는다 — 여기서 보는 것은 배관이다: 조각을 어떻게 나누고,
실패한 조각을 어떻게 버리고, 원값을 어떻게 접는가. 판독의 질 자체는 실호출
프로브로 봤다(모듈 docstring의 실측).
"""

import json
from types import SimpleNamespace

from daedam.eval.expression import (
    ChunkReading,
    FrameImpression,
    MergedAdvice,
    fold,
    judge,
    list_frames,
)


def _frames_dir(tmp_path, count: int, step: float = 3.0):
    directory = tmp_path / "frames"
    directory.mkdir()
    for i in range(count):
        (directory / f"f{i * step:07.1f}.jpg").write_bytes(b"jpg")
    return directory


def _reading(count: int, note: str = "") -> ChunkReading:
    return ChunkReading(
        frames=[
            FrameImpression(
                index=i, confident=20, focused=60, tense=15, flustered=5,
                gaze="screen", note=note,
            )
            for i in range(count)
        ],
        strengths=["차분한 시선"],
        observations=["카메라를 눈높이로"],
    )


class _StubClient:
    """조각 판독과 관찰 취합을 흉내 낸다. 프롬프트를 붙잡아 검증에 쓴다."""

    def __init__(self, fail_from_s: float | None = None) -> None:
        #: 이 경과 초부터 시작하는 조각은 항상 실패한다 — 조각 단위 버림 검증용.
        self.fail_from_s = fail_from_s
        self.prompts: list[str] = []
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        )

    def _parse(self, *, model, messages, response_format, temperature):  # noqa: ANN001
        content = messages[0]["content"]
        if response_format is MergedAdvice:
            self.prompts.append(content)
            parsed = MergedAdvice(strengths=["합쳐진 강점"], observations=["합쳐진 관찰"])
        else:
            header = content[0]["text"]
            self.prompts.append(header)
            images = sum(1 for part in content if part.get("type") == "image_url")
            start = float(header.split("경과 ")[1].split("~")[0])
            if self.fail_from_s is not None and start >= self.fail_from_s:
                raise RuntimeError("판독 실패")
            parsed = _reading(images)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))]
        )


def test_이름이_시각으로_안_읽히는_파일은_건너뛴다(tmp_path) -> None:
    directory = _frames_dir(tmp_path, 2)
    (directory / "fgarbage.jpg").write_bytes(b"x")
    (directory / "cover.jpg").write_bytes(b"x")
    assert [at for at, _ in list_frames(directory)] == [0.0, 3.0]


def test_판독은_시각을_붙여_원값을_남긴다(tmp_path) -> None:
    directory = _frames_dir(tmp_path, 3)
    client = _StubClient()
    result = judge(directory, client=client)
    assert [row["at"] for row in result["frames"]] == [0.0, 3.0, 6.0]
    assert result["frames"][0]["focused"] == 60
    assert result["observations"] == ["카메라를 눈높이로"]
    assert result["strengths"] == ["차분한 시선"]
    # 원값이 파일로 남아야 프롬프트를 고친 뒤 지난 면접을 다시 읽힐 수 있다.
    saved = json.loads((directory / "vlm.json").read_text(encoding="utf-8"))
    assert saved == result


def test_실패한_조각만_버리고_나머지로_접는다(tmp_path) -> None:
    """60장 넘게 만들어 조각을 두 개로 가르고, 뒤 조각만 실패시킨다."""
    directory = _frames_dir(tmp_path, 70)  # 0~207초 → 0~177 / 180~207 두 조각
    client = _StubClient(fail_from_s=180.0)
    result = judge(directory, client=client)
    assert len(result["frames"]) == 60  # 앞 조각만 남는다
    assert max(row["at"] for row in result["frames"]) == 177.0
    # 실패 조각은 한 번 더 시도된다: 성공 1 + 실패 2 + 취합 0 (캡 안이라)
    assert len(client.prompts) == 3


def test_전부_실패하면_None이다(tmp_path) -> None:
    directory = _frames_dir(tmp_path, 3)
    assert judge(directory, client=_StubClient(fail_from_s=0.0)) is None
    assert not (directory / "vlm.json").exists()


def test_빈_디렉터리면_부르지_않는다(tmp_path) -> None:
    directory = tmp_path / "frames"
    directory.mkdir()
    assert judge(directory, client=None) is None  # 클라이언트를 만들 일도 없다


def test_지어낸_프레임_번호는_버린다(tmp_path) -> None:
    directory = _frames_dir(tmp_path, 2)

    class _Wild(_StubClient):
        def _parse(self, *, model, messages, response_format, temperature):  # noqa: ANN001
            reading = _reading(2)
            reading.frames[1].index = 999  # 보낸 적 없는 번호
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(parsed=reading))]
            )

    result = judge(directory, client=_Wild())
    assert [row["at"] for row in result["frames"]] == [0.0]


def test_접기는_배분을_정규화해_평균낸다() -> None:
    judgement = {
        "frames": [
            {"at": 1.0, "confident": 50, "focused": 50, "tense": 0, "flustered": 0},
            {"at": 4.0, "confident": 0, "focused": 100, "tense": 0, "flustered": 0},
        ],
        "observations": ["관찰"],
    }
    folded = fold(judgement)
    assert folded["frames"] == 2
    assert folded["impressions"] == {
        "confident": 0.25, "focused": 0.75, "tense": 0.0, "flustered": 0.0
    }
    assert folded["series"] == ["confident", "focused"]
    assert folded["observations"] == ["관찰"]


def test_접기는_답변_구간으로_자른다() -> None:
    judgement = {
        "frames": [
            {"at": t, "confident": 0, "focused": 100, "tense": 0, "flustered": 0}
            for t in (1.0, 4.0, 7.0, 10.0)
        ],
        "observations": [],
    }
    folded = fold(judgement, [{"startS": 3.0, "endS": 9.0}, {"startS": 100.0, "endS": 110.0}])
    assert folded["answers"][0]["frames"] == 2
    assert folded["answers"][0]["impressions"]["focused"] == 1.0
    # 프레임이 없는 답변은 0으로 — 없는 것을 지어내지 않는다.
    assert folded["answers"][1]["frames"] == 0
    assert folded["answers"][1]["impressions"]["focused"] == 0.0


def test_배분_합이_0인_프레임은_잴_것이_없다() -> None:
    judgement = {
        "frames": [
            {"at": 1.0, "confident": 0, "focused": 0, "tense": 0, "flustered": 0}
        ],
        "observations": [],
    }
    folded = fold(judgement)
    assert folded["frames"] == 0
    assert folded["series"] == []


def test_관찰이_많으면_한_번_합친다(tmp_path) -> None:
    directory = _frames_dir(tmp_path, 70)  # 두 조각 → 관찰이 쌓인다

    class _Chatty(_StubClient):
        def _parse(self, *, model, messages, response_format, temperature):  # noqa: ANN001
            if response_format is MergedAdvice:
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(parsed=MergedAdvice(
                        strengths=["합쳐진 강점"], observations=["합쳐진 관찰"])))])
            content = messages[0]["content"]
            images = sum(1 for part in content if part.get("type") == "image_url")
            reading = _reading(images)
            reading.observations = ["관찰 하나", "관찰 둘", "관찰 셋"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(parsed=reading))]
            )

    result = judge(directory, client=_Chatty())
    assert result["observations"] == ["합쳐진 관찰"]
    assert result["strengths"] == ["합쳐진 강점"]


def test_접기는_시선_방향을_격자로_접는다() -> None:
    """camera와 screen이 둘 다 정면(4)이다 — 웹캠이 화면 위라 화면 응시는
    살짝 아래로 보이는 정면이고, 그것이 화상 면접의 정상 상태다."""
    judgement = {
        "frames": [
            {"at": 1.0, "confident": 0, "focused": 100, "tense": 0, "flustered": 0,
             "gaze": "camera"},
            {"at": 4.0, "confident": 0, "focused": 100, "tense": 0, "flustered": 0,
             "gaze": "screen"},
            {"at": 7.0, "confident": 0, "focused": 100, "tense": 0, "flustered": 0,
             "gaze": "left"},
            {"at": 10.0, "confident": 0, "focused": 100, "tense": 0, "flustered": 0,
             "gaze": "down"},
        ],
        "observations": [],
    }
    folded = fold(judgement, [{"startS": 0.0, "endS": 5.0}])
    gaze = folded["gaze"]
    assert gaze["source"] == "vlm"
    assert gaze["steady"] == 0.5                      # camera + screen
    assert gaze["cells"][3] == 0.25 and gaze["cells"][7] == 0.25
    assert gaze["seconds"] == 12                      # 4장 × 3초
    assert gaze["answers"][0]["steady"] == 1.0        # 앞 두 장만 든 구간


def test_방향이_없는_옛_판독이면_시선_블록이_없다() -> None:
    """gaze 필드가 생기기 전의 vlm.json도 접혀야 한다 — 그때는 홍채 기록이 남는다."""
    judgement = {
        "frames": [
            {"at": 1.0, "confident": 0, "focused": 100, "tense": 0, "flustered": 0}
        ],
        "observations": [],
    }
    assert fold(judgement)["gaze"] is None
