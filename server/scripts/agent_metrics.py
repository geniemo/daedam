"""면접관 에이전트의 행동 지표 — 전사록·피드백(DB)과 서버 로그에서 뽑는다.

    uv run python scripts/agent_metrics.py                       # 로컬 DB
    uv run python scripts/agent_metrics.py --db vm.db --journal vm.log

DB에서 나오는 것(면접마다): 길이, 턴 수, 꼬리질문 비율, 뼈대질문 충실도(툴이 준
문장과 실제 발화의 유사도), 답변 끝→면접관 턴 완료 지연, 지원자 답변 지연, 점수.
로그에서만 나오는 것: 게이트 준수율(질문 발화 앞에 ask_question 호출이 있었나),
파볼 곳 회수율, 필러 재생, 자막 복구, 토큰. 툴 호출 흔적은 로그에만 남는다 —
ADK 세션 이벤트는 면접이 끝나면 지운다.

숫자는 표본 크기와 같이 읽을 것. 한 판으로 "준수율 100%"는 근거가 아니다.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent

#: 뼈대질문으로 보는 유사도 하한. 인사가 붙거나("안녕하십니까. 먼저 …") 토씨가
#: 바뀌어도 넘고, 다른 질문은 못 넘는 선 — 실측 분포로 정했다.
_MATCH = 0.6


def _norm(text: str) -> str:
    return re.sub(r"[\s.,!?…'\"「」·]", "", text)


def _is_question(text: str) -> bool:
    t = text.strip()
    # 마무리 인사는 명령형(~세요)이라 질문 어미와 겹친다 — "들어가세요"는 질문이 아니다.
    if re.search(r"(가십시오|계십시오|감사합니다|들어가세요|가세요|계세요)[.!]?$", t):
        return False
    return "?" in t or bool(re.search(r"(까|나요|세요|주십시오|죠)[.?]?$", t))


def _similarity(utterance: str, pool: list[str]) -> float:
    u = _norm(utterance)
    best = 0.0
    for q in pool:
        n = _norm(q)
        if n and n in u:
            return 1.0
        best = max(best, SequenceMatcher(None, u, n).ratio())
    return best


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 2) if values else None


# ── DB ──────────────────────────────────────────────────────────────────


def db_metrics(path: Path) -> dict:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    pools: dict[str, list[str]] = {}
    for app_id, questions in c.execute("select id, questions from applications where questions is not null"):
        pools[app_id] = [q["text"] for q in json.loads(questions)]
    rows = c.execute(
        "select id, application_id, transcript, feedback from interview_sessions where transcript is not null order by started_at"
    ).fetchall()
    per: list[dict] = []
    for sid, app_id, transcript, feedback in rows:
        t = json.loads(transcript)
        utt = t.get("utterances") or []
        interviewer = [u for u in utt if u["speaker"] == "interviewer"]
        applicant = [u for u in utt if u["speaker"] == "applicant"]
        pool = pools.get(app_id, [])
        questions = [u["text"] for u in interviewer if _is_question(u["text"])]
        sims = [_similarity(q, pool) for q in questions] if pool else []
        skeleton = [s for s in sims if s >= _MATCH]
        # 답변 끝(지원자 전사 시각) → 다음 면접관 턴 완료 시각. 면접관 발화 시작은
        # 기록이 없어 턴 완료로 본다 — 실제 기다림의 상한이다.
        gaps = []
        for i, u in enumerate(utt[:-1]):
            nxt = utt[i + 1]
            if u["speaker"] == "applicant" and nxt["speaker"] == "interviewer":
                d = nxt["at"] - u["at"]
                if 0 < d < 60:
                    gaps.append(d)
        fb = json.loads(feedback) if feedback else None
        voice = (fb or {}).get("voice") or {}
        per.append(
            {
                "session": sid[:8],
                "duration_s": round(t.get("durationS") or 0),
                "turns": len(interviewer),
                "answers": len(applicant),
                "questions": len(questions),
                "skeleton": len(skeleton),
                "followup_ratio": round(1 - len(skeleton) / len(questions), 2) if questions and pool else None,
                "fidelity": round(statistics.mean(skeleton), 2) if skeleton else None,
                "gap_median_s": _median(gaps),
                "start_delay_s": voice.get("meanStartDelayS"),
                "score": ((fb or {}).get("coaching") or {}).get("score"),
                "silent": not applicant,
            }
        )
    refunds = c.execute("select count(*) from credit_entries where reason='refund'").fetchone()[0]
    interviews = c.execute("select count(*) from credit_entries where reason='interview'").fetchone()[0]
    return {"sessions": per, "refunds": refunds, "charged_interviews": interviews}


# ── 로그 ────────────────────────────────────────────────────────────────

_LINE = re.compile(r"^(?P<ts>\S+)\s.*?(?:INFO|WARNING)\s+(?P<logger>[\w.]+):\s(?P<msg>.*)$")


#: 줄 끝의 세션 표지(daedam.logctx). 동시 면접의 로그는 이것으로만 가를 수 있다.
_TAG = re.compile(r" \[session=([0-9a-f]{8})\]$")


def journal_metrics(path: Path) -> dict:
    sessions: dict[str, dict] = {}
    order: list[str] = []
    current: str | None = None

    def bucket(sid: str) -> dict:
        if sid not in sessions:
            sessions[sid] = defaultdict(int, {"session": sid, "evidence": False, "violations": []})
            order.append(sid)
        return sessions[sid]

    for raw in path.read_text(encoding="utf-8").splitlines():
        m = _LINE.match(raw)
        if not m:
            continue
        msg = m.group("msg")
        tagged: str | None = None
        if tag := _TAG.search(msg):
            tagged, msg = tag.group(1), msg[: tag.start()]
        if msg.startswith("면접 시작 ("):
            sid = re.search(r"session=([0-9a-f]+)", msg).group(1)[:8]
            current = sid
            bucket(sid)["connections"] += 1
            continue
        # 표지가 있으면 그 면접, 없으면(옛 로그) 마지막으로 시작한 면접으로 본다.
        sid = tagged or current
        if sid is None:
            continue
        s = bucket(sid)
        if msg.startswith("면접 종료"):
            if sid == current:
                current = None
        elif msg.startswith("뼈대질문") and "배달" in msg:
            s["tool_calls"] += 1
            s["delivered"] += 1
            s["evidence"] = True
        elif msg.startswith("파볼 곳 ") and "개:" in msg:
            n = int(re.search(r"파볼 곳 (\d+)개", msg).group(1))
            s["tool_calls"] += 1
            s["probes"] += n
            s["evidence"] = True
        elif msg.startswith("질문 소진"):
            s["evidence"] = True
        elif msg.startswith("파볼 곳 질문"):
            # 툴이 파볼 곳을 건넨 응답 — 첫 질문·재시도·다음 파볼 곳 모두.
            s["tool_calls"] += 1
            s["evidence"] = True
        # 아래 셋은 ask_question 안에서 찍힌다 — 그 턴에 툴이 돈 증거다. "파볼 곳
        # 질문" 줄이 없던 로그에서는 이것이 유일한 흔적이다(다음 파볼 곳을 건넨
        # 응답은 로그가 없었다).
        elif msg.startswith("파볼 곳 확인"):
            s["probe_ok"] += 1
            s["evidence"] = True
        elif msg.startswith("파볼 곳 포기"):
            s["probe_giveup"] += 1
            s["evidence"] = True
        elif msg.startswith("answered 누락"):
            s["answered_missing"] += 1
            s["evidence"] = True
        elif msg.startswith("필러 재생"):
            s["fillers"] += 1
        elif msg.startswith("지식 검색"):
            s["searches"] += 1
        elif msg.startswith("면접관(음성으로 복구)"):
            s["recovered"] += 1
        elif msg.startswith("면접관:"):
            text = msg[len("면접관:"):].strip()
            s["said"] += 1
            # 앞 발화의 꼬리를 그대로 이어받아 시작하면(전사 끊김·끼어들기 뒤의 이어 말함)
            # 같은 질문이다 — 게이트 판정에서 뺀다. 옛 로그에만 있는 모양이다.
            prev = _norm(s.get("last_text", "") or "")
            head = _norm(text)
            continued = bool(prev) and any(head.startswith(prev[-n:]) for n in range(4, min(len(prev), 30) + 1))
            s["last_text"] = text
            if _is_question(text):
                if continued:
                    s["continued"] += 1
                elif s["evidence"]:
                    s["question_turns"] += 1
                    s["gated"] += 1
                    # 툴 응답 하나는 질문 하나를 허락한다 — 질문이 근거를 쓴다.
                    # 턴 완료로 지우지 않는 이유: 끼어들기로 턴 완료가 빠지면 앞
                    # 발화의 턴이 툴 호출 턴과 합쳐져 근거가 엉뚱한 때 지워졌다(실측 1건).
                    s["evidence"] = False
                else:
                    s["question_turns"] += 1
                    s["violations"].append(text[:50])
        elif msg.startswith("턴 완료"):
            s["turns"] += 1
        elif msg.startswith("토큰 사용"):
            mm = re.search(r"입력 (\d+).*출력 (\d+)", msg)
            if mm:
                s["tokens_in"] += int(mm.group(1))
                s["tokens_out"] += int(mm.group(2))
    return {"sessions": [dict(sessions[k]) for k in order]}


# ── 출력 ────────────────────────────────────────────────────────────────


def _table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body = []
    for r in rows:
        body.append("| " + " | ".join("" if r.get(k) is None else str(r.get(k)) for k, _ in columns) + " |")
    return "\n".join([head, sep, *body])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(_SERVER_DIR / "data" / "daedam.db"))
    parser.add_argument("--journal", help="journalctl -u daedam -o short-iso 출력 파일")
    parser.add_argument("--min-turns", type=int, default=3, help="이보다 짧은 판은 시험으로 보고 뺀다")
    args = parser.parse_args()

    db = db_metrics(Path(args.db))
    kept = [s for s in db["sessions"] if s["turns"] >= args.min_turns and not s["silent"]]
    dropped = len(db["sessions"]) - len(kept)
    print(f"## 전사록·피드백 지표 (DB: {args.db})\n")
    print(f"면접 {len(db['sessions'])}판 중 {len(kept)}판 (턴 {args.min_turns}개 미만·무응답 {dropped}판 제외)\n")
    print(_table(kept, [("session", "판"), ("duration_s", "길이(초)"), ("turns", "면접관 턴"), ("answers", "답변"), ("questions", "질문"), ("skeleton", "뼈대질문"), ("followup_ratio", "꼬리질문 비율"), ("fidelity", "충실도"), ("gap_median_s", "답변 끝→턴 완료(초)"), ("start_delay_s", "답변 지연(초)"), ("score", "점수")]))
    q = sum(s["questions"] for s in kept if s["followup_ratio"] is not None)
    sk = sum(s["skeleton"] for s in kept if s["followup_ratio"] is not None)
    fid = [s["fidelity"] for s in kept if s["fidelity"] is not None]
    gaps = [s["gap_median_s"] for s in kept if s["gap_median_s"] is not None]
    delays = [s["start_delay_s"] for s in kept if s["start_delay_s"] is not None]
    scores = [s["score"] for s in kept if s["score"] is not None]
    print("\n**합계**")
    print(f"- 면접관 턴 {sum(s['turns'] for s in kept)}개, 질문 {q}개 중 뼈대질문 {sk}개 → 꼬리질문 비율 {1 - sk / q:.0%}" if q else "- 질문 풀이 남은 판이 없어 꼬리질문 비율을 못 낸다")
    print(f"- 뼈대질문 충실도 평균 {statistics.mean(fid):.2f} (1 = 툴이 준 문장 그대로)" if fid else "- 충실도: 없음")
    print(f"- 답변 끝→면접관 턴 완료 중앙값 {statistics.median(gaps):.1f}초 (판별 중앙값의 중앙값)" if gaps else "- 지연: 없음")
    print(f"- 지원자 답변 지연 평균 {statistics.mean(delays):.1f}초" if delays else "- 답변 지연: 없음")
    print(f"- 점수 평균 {statistics.mean(scores):.0f} (최저 {min(scores)} · 최고 {max(scores)})" if scores else "- 점수: 없음")
    print(f"- 무응답 판 {sum(1 for s in db['sessions'] if s['silent'])}개 · 과금 {db['charged_interviews']}건 중 환불 {db['refunds']}건")

    if args.journal:
        jm = journal_metrics(Path(args.journal))
        rows = [s for s in jm["sessions"] if s.get("said", 0) >= args.min_turns]
        print(f"\n## 로그 지표 (journal: {args.journal})\n")
        for r in rows:
            r["gate"] = f"{r['gated']}/{r['question_turns']}" if r.get("question_turns") else None
            r["probe"] = f"확인 {r.get('probe_ok', 0)} · 포기 {r.get('probe_giveup', 0)} · 누락 {r.get('answered_missing', 0)}"
            r["tokens"] = f"{r.get('tokens_in', 0):,} / {r.get('tokens_out', 0):,}"
        print(_table(rows, [("session", "판"), ("connections", "커넥션"), ("turns", "턴"), ("said", "발화"), ("question_turns", "질문 발화"), ("gate", "게이트 준수"), ("tool_calls", "툴 호출"), ("delivered", "뼈대 배달"), ("probes", "파볼 곳"), ("probe", "파볼 곳 결과"), ("fillers", "필러"), ("searches", "지식 검색"), ("continued", "이어 말함"), ("recovered", "자막 복구"), ("tokens", "토큰 입력/출력")]))
        gated = sum(r.get("gated", 0) for r in rows)
        qt = sum(r.get("question_turns", 0) for r in rows)
        print("\n**합계**")
        print(f"- 게이트 준수율 {gated}/{qt} = {gated / qt:.0%}" if qt else "- 질문 발화 없음")
        for r in rows:
            for v in r.get("violations", []):
                print(f"  - 위반 ({r['session']}): {v}")
        print(f"- 파볼 곳 {sum(r.get('probes', 0) for r in rows)}개 추출 → 확인 {sum(r.get('probe_ok', 0) for r in rows)} · 포기 {sum(r.get('probe_giveup', 0) for r in rows)} · answered 누락 {sum(r.get('answered_missing', 0) for r in rows)}")
        print(f"- 툴 호출 {sum(r.get('tool_calls', 0) for r in rows)}회 · 필러 재생 {sum(r.get('fillers', 0) for r in rows)}회 · 자막 복구 {sum(r.get('recovered', 0) for r in rows)}회")


if __name__ == "__main__":
    main()
