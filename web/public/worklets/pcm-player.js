/**
 * Model-voice playback worklet — queued 16-bit PCM → Float32 out.
 *
 * The AudioContext that loads this MUST be
 * `new AudioContext({ sampleRate: 24000 })`. Live API output is 16-bit PCM /
 * 24kHz / mono — a different rate from the 16kHz input, which is why the app
 * runs two AudioContexts rather than one.
 *
 * Why a worklet and not `AudioBufferSourceNode.start()` per chunk: chunks
 * arrive over a WebSocket at irregular intervals, and scheduling each one
 * independently leaves audible seams. Here a single continuous ring drains
 * whatever has arrived and emits silence when it runs dry.
 *
 * `flush` is the barge-in path. When the server relays Live API's
 * `interrupted` signal, every already-buffered sample must be dropped
 * immediately — otherwise the agent keeps talking over the user, which is the
 * single most common way a voice demo reads as broken.
 */
class PCMPlayer extends AudioWorkletProcessor {
  constructor() {
    super()
    /** @type {Float32Array[]} */
    this.queue = []
    this.readIndex = 0
    this.playing = false

    this.port.onmessage = (e) => {
      const msg = e.data
      if (msg?.type === 'chunk') {
        const pcm = new Int16Array(msg.pcm)
        const f32 = new Float32Array(pcm.length)
        for (let i = 0; i < pcm.length; i++) f32[i] = pcm[i] / 0x8000
        this.queue.push(f32)
      } else if (msg?.type === 'flush') {
        this.queue = []
        this.readIndex = 0
        this.notify(false)
      }
    }
  }

  notify(playing) {
    if (playing !== this.playing) {
      this.playing = playing
      // Drives the 'speaking' | 'listening' indicator without polling.
      this.port.postMessage({ type: 'playing', value: playing })
    }
  }

  process(_inputs, outputs) {
    const out = outputs[0][0]
    if (!out) return true

    let written = 0
    while (written < out.length && this.queue.length > 0) {
      const head = this.queue[0]
      const available = head.length - this.readIndex
      const need = out.length - written
      const take = Math.min(available, need)

      out.set(head.subarray(this.readIndex, this.readIndex + take), written)
      written += take
      this.readIndex += take

      if (this.readIndex >= head.length) {
        this.queue.shift()
        this.readIndex = 0
      }
    }

    // Underrun → silence rather than a click.
    if (written < out.length) out.fill(0, written)

    this.notify(this.queue.length > 0)
    return true
  }
}

registerProcessor('pcm-player', PCMPlayer)
