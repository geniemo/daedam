"""면접 기록 테스트.

면접이 끝난 뒤 리포트가 설 자리라, 여기서 잃으면 되돌릴 방법이 없다.
"""

import json
import wave

from daedam.server.recording import SAMPLE_RATE, SAMPLE_WIDTH, InterviewRecording


def _frames(seconds: float) -> bytes:
    return b"\x00\x01" * int(SAMPLE_RATE * seconds)


def test_경과는_벽시계가_아니라_쓴_바이트로_잰다(tmp_path) -> None:
    """재접속 사이의 공백만큼 벽시계는 어긋난다. 오디오 안의 위치가 기준이다."""
    recording = InterviewRecording(directory=tmp_path)
    recording.write_audio(_frames(1.5))
    assert recording.elapsed_s == 1.5


def test_전사는_오디오_위치와_함께_남는다(tmp_path) -> None:
    recording = InterviewRecording(directory=tmp_path)
    recording.note("interviewer", "자기소개 부탁드립니다.")
    recording.write_audio(_frames(3.0))
    recording.note("applicant", "네, 저는")

    assert [(u.speaker, u.at) for u in recording.utterances] == [
        ("interviewer", 0.0),
        ("applicant", 3.0),
    ]


def test_빈_전사는_적지_않는다(tmp_path) -> None:
    recording = InterviewRecording(directory=tmp_path)
    recording.note("applicant", "   ")
    recording.note("applicant", "")
    assert recording.utterances == []


def test_재접속하면_이어_쓴다(tmp_path) -> None:
    """Live 커넥션 수명이 ~10분이라 15~20분 면접은 반드시 재접속한다."""
    first = InterviewRecording(directory=tmp_path)
    first.write_audio(_frames(2.0))

    revived = InterviewRecording(directory=tmp_path)
    assert revived.elapsed_s == 2.0
    revived.write_audio(_frames(1.0))
    assert revived.elapsed_s == 3.0


def test_재접속해도_앞_커넥션의_전사를_잃지_않는다(tmp_path) -> None:
    """바이트만 이어받고 전사를 두고 오면 다음 저장이 앞의 발화를 덮어쓴다."""
    first = InterviewRecording(directory=tmp_path)
    first.note("interviewer", "자기소개 부탁드립니다.")
    first.write_audio(_frames(2.0))
    first.note("applicant", "네, 저는")
    first.finish()

    revived = InterviewRecording(directory=tmp_path)
    revived.write_audio(_frames(1.0))
    revived.note("applicant", "이어서 말합니다")
    revived.finish()

    saved = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert [u["text"] for u in saved["utterances"]] == [
        "자기소개 부탁드립니다.",
        "네, 저는",
        "이어서 말합니다",
    ]
    assert saved["utterances"][-1]["at"] == 3.0


def test_끝나면_재생용_wav와_전사가_남는다(tmp_path) -> None:
    recording = InterviewRecording(directory=tmp_path)
    recording.note("interviewer", "자기소개 부탁드립니다.")
    recording.write_audio(_frames(2.0))
    recording.note("applicant", "네, 물류 데이터 분석 프로젝트를 했습니다.")
    recording.finish()

    with wave.open(str(tmp_path / "mic.wav"), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == SAMPLE_RATE
        assert wav.getsampwidth() == SAMPLE_WIDTH
        assert wav.getnframes() == int(SAMPLE_RATE * 2.0)

    saved = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert saved["durationS"] == 2.0
    assert [u["speaker"] for u in saved["utterances"]] == ["interviewer", "applicant"]
    assert saved["utterances"][1]["at"] == 2.0


def test_원본_pcm은_지우지_않는다(tmp_path) -> None:
    """wav 생성이 틀려도 원본이 있으면 되살릴 수 있다."""
    recording = InterviewRecording(directory=tmp_path)
    recording.write_audio(_frames(0.5))
    recording.finish()
    assert (tmp_path / "mic.pcm").exists()


def test_소리가_하나도_없어도_전사는_저장된다(tmp_path) -> None:
    recording = InterviewRecording(directory=tmp_path)
    recording.note("interviewer", "안녕하세요.")
    recording.finish()

    saved = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert saved["durationS"] == 0.0
    assert len(saved["utterances"]) == 1
    assert not (tmp_path / "mic.wav").exists()


def test_쓰는_동안_파일을_열어_둔다(tmp_path) -> None:
    """프레임마다 열고 닫으면 그 동기 I/O가 브리지 이벤트 루프를 막는다."""
    recording = InterviewRecording(directory=tmp_path)
    recording.write_audio(_frames(0.1))
    assert recording._handle is not None
    recording.write_audio(_frames(0.1))
    assert recording._handle is not None

    recording.finish()
    # wav는 버퍼가 비워진 뒤에 만들어져야 한다 — 안 그러면 뒷부분이 빈다.
    assert recording._handle is None
    with wave.open(str(tmp_path / "mic.wav"), "rb") as wav:
        assert wav.getnframes() == int(SAMPLE_RATE * 0.2)
