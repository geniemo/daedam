# 모델 평가 리포트 집계 — 벤치·라이브 JSONL을 읽어 통계표(stdout)와 차트 PNG(reports/) 생성
# 입력: data/metrics/bench-llm-20260721.jsonl (오프라인 TTFT 벤치, 모델당 15회)
#       data/metrics/20260721-cascade.jsonl   (라이브 세션 턴별 구간 지연)
# 사용: .venv/bin/python scripts/report_model_eval.py
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "metrics" / "bench-llm-20260721.jsonl"
LIVE = ROOT / "data" / "metrics" / "20260721-cascade.jsonl"
OUT = ROOT / "reports"

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

# 라이브 평가 세션 room → 모델 (아침의 모델 태깅 이전 데이터·스모크 세션은 제외)
SESSIONS = {
    "console-d193b3f2": "grok-4-1-fast-non-reasoning",
    "console-2f7af365": "grok-4.20-0309-non-reasoning",
    "console-b69e0a3d": "grok-4.5",
}
SHORT = {
    "grok-4-1-fast-non-reasoning": "4-1-fast-nr",
    "grok-4.20-0309-non-reasoning": "4.20-nr",
    "grok-4.3": "4.3",
    "grok-4.5": "4.5",
    "grok-build-0.1": "build-0.1",
}


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * (len(xs) - 1)))]


def load(path):
    return [json.loads(l) for l in path.open(encoding="utf-8")]


BENCH_EXCLUDE = {"grok-build-0.1"}  # 용도 불명(코딩용 추정)·음성 부적합 확정 → 리포트에서 제외


def bench_stats():
    rows = [r for r in load(BENCH) if not r["warmup"] and r.get("ttft") is not None
            and r["model"] not in BENCH_EXCLUDE]
    out = {}
    for m in dict.fromkeys(r["model"] for r in rows):  # 등장 순서 유지
        ts = [r["ttft"] for r in rows if r["model"] == m]
        out[m] = {"n": len(ts), "mean": st.mean(ts), "med": st.median(ts),
                  "p95": p95(ts), "min": min(ts), "max": max(ts), "raw": ts}
    return out


def live_stats():
    rows = [r for r in load(LIVE) if r.get("room") in SESSIONS and r.get("eou_delay") is not None]
    out = {}
    for room, model in SESSIONS.items():
        rs = [r for r in rows if r["room"] == room]
        totals = [r["total"] for r in rs if r.get("total") is not None]
        out[model] = {
            "n": len(rs),
            "total_med": st.median(totals), "total_min": min(totals), "total_max": max(totals),
            "ttft_med": st.median(r["llm_ttft"] for r in rs),
            "eou_med": st.median(r["eou_delay"] for r in rs),
            "ttfb_med": st.median(r["tts_ttfb"] for r in rs),
            "totals": totals,
        }
    return out


def chart_bench(bench):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    models = list(bench)
    ax.boxplot([bench[m]["raw"] for m in models], tick_labels=[SHORT[m] for m in models],
               showfliers=True, medianprops={"color": "#d62728"})
    ax.set_ylabel("LLM TTFT (초)")
    ax.set_title("Grok 모델별 LLM TTFT — 오프라인 벤치 (모델당 15회, 동일 프롬프트)")
    ax.axhline(1.0, color="gray", ls="--", lw=0.8)
    ax.annotate("1초", xy=(0.02, 1.0), xycoords=("axes fraction", "data"),
                va="bottom", fontsize=8, color="gray")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "bench-ttft-20260721.png", dpi=150)


def chart_live(live):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    common = min(len(s["totals"]) for s in live.values())  # 세션 길이가 달라 공통 구간만 비교
    for m, s in live.items():
        ax1.plot(range(1, common + 1), s["totals"][:common], marker="o", ms=4, label=SHORT[m])
    ax1.set_xlabel("턴 순서")
    ax1.set_ylabel("발화 종료 → 첫 오디오 (초)")
    ax1.set_title(f"라이브 세션 턴별 총 지연 (공통 구간 처음 {common}턴)")
    ax1.axhline(0.78, color="gray", ls="--", lw=0.8)
    ax1.annotate("Grok 네이티브 TTFA 0.78s", xy=(0.02, 0.80), xycoords=("axes fraction", "data"),
                 va="bottom", fontsize=8, color="gray")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    models = list(live)
    x = range(len(models))
    eou = [live[m]["eou_med"] for m in models]
    ttft = [live[m]["ttft_med"] for m in models]
    ttfb = [live[m]["ttfb_med"] for m in models]
    ax2.bar(x, eou, 0.55, label="턴 감지 (EOU)", color="#8da0cb")
    ax2.bar(x, ttft, 0.55, bottom=eou, label="LLM TTFT", color="#fc8d62")
    ax2.bar(x, ttfb, 0.55, bottom=[a + b for a, b in zip(eou, ttft)], label="TTS TTFB", color="#66c2a5")
    ax2.set_xticks(list(x), [SHORT[m] for m in models])
    ax2.set_ylabel("중앙값 (초)")
    ax2.set_title("구간별 지연 중앙값")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "live-latency-20260721.png", dpi=150)


def main():
    OUT.mkdir(exist_ok=True)
    bench, live = bench_stats(), live_stats()

    print("## 오프라인 벤치 (LLM TTFT, 초)")
    for m, s in bench.items():
        print(f"{m:34s} n={s['n']:2d} mean={s['mean']:.2f} med={s['med']:.2f} "
              f"p95={s['p95']:.2f} min={s['min']:.2f} max={s['max']:.2f}")
    print("\n## 라이브 세션 (실턴, 초)")
    for m, s in live.items():
        print(f"{m:34s} n={s['n']:2d} total med={s['total_med']:.2f} "
              f"[{s['total_min']:.2f}~{s['total_max']:.2f}] | eou={s['eou_med']:.2f} "
              f"ttft={s['ttft_med']:.2f} ttfb={s['ttfb_med']:.2f}")

    chart_bench(bench)
    chart_live(live)
    print(f"\n차트 저장: {OUT.relative_to(ROOT)}/bench-ttft-20260721.png, live-latency-20260721.png")


if __name__ == "__main__":
    main()
