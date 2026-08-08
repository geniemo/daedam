/**
 * Mic capture worklet — Float32 → 16-bit PCM.
 *
 * The AudioContext that loads this MUST be constructed as
 * `new AudioContext({ sampleRate: 16000 })`. ADK performs no format
 * conversion: "Sending audio in incorrect formats will result in poor quality
 * or errors." Live API input spec is 16-bit PCM / 16kHz / mono.
 *
 * Chunk size is fixed at 1280 samples (80ms, 2560 bytes) — inside ADK's
 * recommended 50–100ms band, and an exact multiple of the 128-sample render
 * quantum so no frame is ever split. Keep it constant for the whole session;
 * ADK notes varying chunk sizes degrade performance.
 *
 * Runs on the audio thread, so UI work never causes a dropout.
 */
const CHUNK_SAMPLES = 1280

class PCMRecorder extends AudioWorkletProcessor {
  constructor() {
    super()
    this.buffer = new Int16Array(CHUNK_SAMPLES)
    this.offset = 0
    this.muted = false
    this.port.onmessage = (e) => {
      if (e.data?.type === 'mute') this.muted = !!e.data.value
    }
  }

  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel) return true

    // 일시정지 중에는 마이크 프레임을 버립니다 — 연결은 유지한 채로.
    if (this.muted) return true

    for (let i = 0; i < channel.length; i++) {
      // Web Audio gives Float32 in [-1, 1]; × 32767 → int16.
      const s = Math.max(-1, Math.min(1, channel[i]))
      this.buffer[this.offset++] = s < 0 ? s * 0x8000 : s * 0x7fff

      if (this.offset === CHUNK_SAMPLES) {
        // Transfer the underlying buffer — no copy, no GC churn per chunk.
        const out = this.buffer.buffer
        this.port.postMessage({ type: 'chunk', pcm: out }, [out])
        this.buffer = new Int16Array(CHUNK_SAMPLES)
        this.offset = 0
      }
    }
    return true
  }
}

registerProcessor('pcm-recorder', PCMRecorder)
