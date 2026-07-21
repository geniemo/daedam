# Grok 모델별 LLM TTFT 벤치마크 (오프라인 스크립트 — 라이브 세션과 무관)
# 측정 설계: 모델당 워밍업 1회(제외) + 15회, 라운드로빈 인터리빙(시간대 편향 분산),
#            keep-alive 연결 재사용(워커의 지속 연결과 동일 조건), mean/med/p95 보고
# TTFT 정의: 첫 "본문" 델타까지 — reasoning 델타(reasoning_content 등)는 음성으로 나갈 수 없으므로 제외
# 확인 문서 (2026-07-21):
# - https://docs.x.ai/docs/guides/streaming-response  (SSE 스트리밍)
# - https://docs.livekit.io/agents/models/llm/plugins/xai/  (워커는 Responses API 사용 → 동일 경로 우선)
# - 실측 확인: /v1/responses는 typed 이벤트(response.output_text.delta), /v1/chat/completions는 choices[].delta
# 사용: .venv/bin/python scripts/bench_llm_ttft.py [모델 ...] (기본: CANDIDATES)
import json
import os
import statistics as st
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ["XAI_API_KEY"]
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
OUT = ROOT / "data" / "metrics" / f"bench-llm-{datetime.now(timezone.utc):%Y%m%d}.jsonl"

CANDIDATES = [
    "grok-4-1-fast-non-reasoning",  # 현 워커 기본값(별칭) — 기준선
    "grok-4.20-0309-non-reasoning",
    "grok-4.3",
    "grok-4.5",
    "grok-build-0.1",
]
RUNS = 15
GAP = 0.3
MAX_TOKENS = 400  # reasoning 모델이 생각을 마치고 본문에 도달할 여유
SYSTEM = "당신은 한국어 모의면접 면접관입니다. 지원자의 답변에 두 문장 이내의 짧은 꼬리질문으로만 응답합니다."
USER = "저는 백엔드 개발자로 3년간 결제 시스템을 운영했고, 장애 대응 과정에서 재발 방지 프로세스를 만든 경험이 있습니다."

try:
    import httpx
    _client = httpx.Client(timeout=60)
except ImportError:
    _client = None


class HTTPCodeError(Exception):
    def __init__(self, code: int):
        self.code = code


def _content_delta(payload: str) -> bool:
    """이 SSE data 페이로드가 '본문' 델타면 True (reasoning 델타는 False)."""
    try:
        d = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return False
    # Responses API: {"type": "response.output_text.delta", "delta": "..."}
    if d.get("type") == "response.output_text.delta" and d.get("delta"):
        return True
    # chat completions: {"choices": [{"delta": {"content": "..."}}]}
    choices = d.get("choices")
    if choices:
        return bool(choices[0].get("delta", {}).get("content"))
    return False


def _iter_data_lines(url: str, body: dict):
    if _client is not None:
        with _client.stream("POST", url, json=body, headers=HEADERS) as r:
            if r.status_code >= 400:
                raise HTTPCodeError(r.status_code)
            for line in r.iter_lines():
                yield line.strip()
    else:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw in resp:
                    yield raw.decode("utf-8", "ignore").strip()
        except urllib.error.HTTPError as e:
            raise HTTPCodeError(e.code)


def sse_ttft(url: str, body: dict) -> tuple[float | None, float]:
    """스트리밍 요청 → (첫 본문 delta까지 초, 전체 완료까지 초)."""
    t0 = time.perf_counter()
    ttft = None
    for line in _iter_data_lines(url, body):
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        if ttft is None and _content_delta(payload):
            ttft = time.perf_counter() - t0
    return ttft, time.perf_counter() - t0


def attempts_for(model: str) -> list[tuple[str, dict]]:
    return [
        ("https://api.x.ai/v1/responses",
         {"model": model, "input": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
          "stream": True, "max_output_tokens": MAX_TOKENS}),
        ("https://api.x.ai/v1/chat/completions",
         {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
          "stream": True, "max_tokens": MAX_TOKENS}),
    ]


_endpoint_cache: dict[str, int] = {}  # model → 성공한 attempt 인덱스


def measure(model: str, run: int, warmup: bool = False) -> dict:
    base = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model, "run": run, "warmup": warmup}
    attempts = attempts_for(model)
    start = _endpoint_cache.get(model, 0)
    for idx in range(start, len(attempts)):
        url, body = attempts[idx]
        try:
            ttft, total = sse_ttft(url, body)
            _endpoint_cache[model] = idx
            return {**base, "endpoint": url.rsplit("/", 1)[-1], "ttft": ttft, "gen_total": round(total, 3)}
        except HTTPCodeError as e:
            if idx == 0 and e.code in (400, 404, 422):
                continue  # Responses 미지원 모델 → chat completions 폴백
            return {**base, "error": f"HTTP {e.code}"}
        except Exception as e:
            return {**base, "error": type(e).__name__}
    return {**base, "error": "모든 엔드포인트 실패"}


def main():
    models = sys.argv[1:] or CANDIDATES
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    with OUT.open("a", encoding="utf-8") as f:
        def record(row):
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()  # 라운드 중단 시에도 원본 보존

        for m in models:  # 워밍업 — 연결 수립 비용 제외, 스코어링 안 함
            record(measure(m, -1, warmup=True))
            time.sleep(GAP)

        for i in range(RUNS):  # 라운드로빈 인터리빙
            for m in models:
                record(measure(m, i))
                time.sleep(GAP)
            print(f"라운드 {i + 1}/{RUNS} 완료", flush=True)

    print()
    for m in models:
        ok = sorted(r["ttft"] for r in rows
                    if r["model"] == m and not r["warmup"] and r.get("ttft") is not None)
        errs = sum(1 for r in rows if r["model"] == m and not r["warmup"] and "error" in r)
        if ok:
            p95 = ok[min(len(ok) - 1, int(0.95 * (len(ok) - 1)))]
            ep = next(r["endpoint"] for r in rows if r["model"] == m and "endpoint" in r)
            print(f"{m:34s} n={len(ok)} mean={st.mean(ok):.2f} med={st.median(ok):.2f} "
                  f"p95={p95:.2f} min={ok[0]:.2f} max={ok[-1]:.2f} 오류={errs} ({ep})")
        else:
            first_err = next((r["error"] for r in rows if r["model"] == m and "error" in r), "본문 delta 미검출")
            print(f"{m:34s} 실패: {first_err}")

    print(f"\n원본 {len(rows)}행 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
