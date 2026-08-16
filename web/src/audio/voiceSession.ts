import type { Connection, Phase, SessionInfo } from '@/store/interview'

/**
 * Browser half of the voice session.
 *
 * Transport: binary WebSocket frames to the ADK/FastAPI server, which owns the
 * Gemini Live session via `run_live`. Binary rather than base64-in-JSON — ADK
 * measures that at ~33% less bandwidth plus no encode/decode cost.
 *
 * Wire format (server-defined, kept deliberately small):
 *   client → server : raw ArrayBuffer  = 16kHz PCM chunk
 *                     JSON text frame  = control ({type:'start'|'end'})
 *   server → client : raw ArrayBuffer  = 24kHz PCM chunk
 *                     JSON text frame  = events (session / phase / question /
 *                                        caption / interrupted / resumeToken /
 *                                        goAway)
 *
 * `session` arrives first on every connection and carries the interview's
 * progress (남은 시간·단계·질문 번호). The server owns that clock — on a
 * reconnect the screen picks up where the interview actually is.
 */

export interface VoiceSessionHandlers {
  onConnection?: (c: Connection) => void
  onSession?: (info: SessionInfo) => void
  onPhase?: (p: Phase) => void
  onQuestion?: (index: number, stage: number) => void
  onCaption?: (text: string, final: boolean) => void
  onResumeToken?: (token: string) => void
  onEnded?: () => void
  onError?: (err: Error) => void
}

export interface VoiceSessionOptions {
  url?: string
  cardId: string
  handlers: VoiceSessionHandlers
}

const INPUT_RATE = 16_000
const OUTPUT_RATE = 24_000
const MAX_BACKOFF_MS = 8_000

export class VoiceSession {
  private opts: VoiceSessionOptions
  private ws: WebSocket | null = null

  private inCtx: AudioContext | null = null
  private outCtx: AudioContext | null = null
  private stream: MediaStream | null = null
  private recorder: AudioWorkletNode | null = null
  private player: AudioWorkletNode | null = null

  /** Live amplitude taps. Read from rAF via `levels()` — never through React state. */
  private inAnalyser: AnalyserNode | null = null
  private outAnalyser: AnalyserNode | null = null
  private inBuf = new Uint8Array(0)
  private outBuf = new Uint8Array(0)

  private resumeToken: string | null = null
  private retries = 0
  private closing = false

  constructor(opts: VoiceSessionOptions) {
    this.opts = opts
  }

  /**
   * MUST be called from inside a user-gesture handler ("면접 시작하기" click).
   * An AudioContext created outside one starts suspended and the whole session
   * is silent with no error to point at.
   */
  async start(): Promise<void> {
    this.closing = false
    this.opts.handlers.onConnection?.('connecting')

    // Echo cancellation matters more than usual here: the model's own voice
    // coming out of the speakers is picked up by the mic and trips VAD, so the
    // agent interrupts itself. Headphones remain the safe demo setup.
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })

    // stop()이 start() 완료 전에 불렸다면(StrictMode 이중 마운트) 여기서
    // 멈춘다 — 계속 진행하면 아무도 참조하지 않는 유령 세션이 소켓까지 열어
    // 목소리가 겹치고, 화면을 나가도 계속 떠든다.
    if (this.closing) {
      this.stream.getTracks().forEach((t) => t.stop())
      this.stream = null
      return
    }

    this.inCtx = new AudioContext({ sampleRate: INPUT_RATE })
    this.outCtx = new AudioContext({ sampleRate: OUTPUT_RATE })
    await Promise.all([this.inCtx.resume(), this.outCtx.resume()])

    await this.inCtx.audioWorklet.addModule('/worklets/pcm-recorder.js')
    await this.outCtx.audioWorklet.addModule('/worklets/pcm-player.js')

    const source = this.inCtx.createMediaStreamSource(this.stream)
    this.inAnalyser = this.inCtx.createAnalyser()
    this.inAnalyser.fftSize = 256
    this.inAnalyser.smoothingTimeConstant = 0.7
    this.inBuf = new Uint8Array(this.inAnalyser.frequencyBinCount)

    this.recorder = new AudioWorkletNode(this.inCtx, 'pcm-recorder')
    this.recorder.port.onmessage = (e) => {
      if (e.data?.type === 'chunk') this.sendBinary(e.data.pcm as ArrayBuffer)
    }
    source.connect(this.inAnalyser)
    this.inAnalyser.connect(this.recorder)

    this.player = new AudioWorkletNode(this.outCtx, 'pcm-player')
    this.outAnalyser = this.outCtx.createAnalyser()
    this.outAnalyser.fftSize = 256
    this.outAnalyser.smoothingTimeConstant = 0.75
    this.outBuf = new Uint8Array(this.outAnalyser.frequencyBinCount)
    this.player.port.onmessage = (e) => {
      if (e.data?.type === 'playing') {
        this.opts.handlers.onPhase?.(e.data.value ? 'speaking' : 'listening')
      }
    }
    this.player.connect(this.outAnalyser)
    this.outAnalyser.connect(this.outCtx.destination)

    this.connect()
  }

  private wsUrl(): string {
    if (this.opts.url) return this.opts.url
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams({ card: this.opts.cardId })
    if (this.resumeToken) params.set('resume', this.resumeToken)
    return `${scheme}://${location.host}/ws/interview?${params}`
  }

  private connect(): void {
    // start()와 재연결 타이머 어느 경로로 오든, 닫히는 중이면 소켓을 새로
    // 열지 않는다. 남은 자원(마이크·컨텍스트)은 stop()이 마저 정리한다.
    if (this.closing) {
      void this.stop()
      return
    }
    const ws = new WebSocket(this.wsUrl())
    ws.binaryType = 'arraybuffer'
    this.ws = ws

    ws.onopen = () => {
      this.retries = 0
      this.opts.handlers.onConnection?.('live')
      ws.send(JSON.stringify({ type: 'start' }))
    }

    ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) {
        this.player?.port.postMessage({ type: 'chunk', pcm: e.data }, [e.data])
        return
      }
      let msg: Record<string, unknown>
      try {
        msg = JSON.parse(e.data as string)
      } catch {
        return
      }
      switch (msg.type) {
        // First frame of every connection — the interview's own clock.
        case 'session':
          this.opts.handlers.onSession?.(msg as unknown as SessionInfo)
          break
        case 'phase':
          this.opts.handlers.onPhase?.(msg.value as Phase)
          break
        case 'question':
          this.opts.handlers.onQuestion?.(msg.index as number, msg.stage as number)
          break
        case 'caption':
          this.opts.handlers.onCaption?.(msg.text as string, msg.final as boolean)
          break
        // Live API `interrupted`: drop every buffered sample right now.
        case 'interrupted':
          this.player?.port.postMessage({ type: 'flush' })
          this.opts.handlers.onPhase?.('listening')
          break
        // Resumption token, valid 2 hours. Survives a reconnect to a different
        // Cloud Run instance (session affinity there is best-effort only).
        case 'resumeToken':
          this.resumeToken = msg.token as string
          this.opts.handlers.onResumeToken?.(msg.token as string)
          break
        // GoAway.timeLeft — reconnect before we are cut off, not after.
        case 'goAway':
          this.reconnect()
          break
        case 'ended':
          this.closing = true
          this.opts.handlers.onEnded?.()
          break
      }
    }

    ws.onerror = () => this.opts.handlers.onError?.(new Error('voice socket error'))

    ws.onclose = (event) => {
      // 우리가 닫은 경우(stop, 또는 ended를 이미 받은 경우)는 여기서 끝내기만
      // 한다 — 면접을 취소하고 나가는 것도 이 경로라, 종료를 다시 알리면 홈에
      // 있는 사용자를 결과 화면으로 끌고 간다.
      if (this.closing) {
        this.opts.handlers.onConnection?.('ended')
        return
      }
      // 서버가 정상 종료(1000)로 닫았다면 면접이 끝난 것이다. ended 프레임이
      // 유실되거나 서버가 먼저 닫아도 화면이 면접에 갇히지 않게 여기서도 끝으로
      // 본다 — onEnded는 중복 호출을 스스로 막는다. 재접속은 사고로 끊긴
      // 경우(1006 등)에만 남는다.
      if (event.code === 1000) {
        this.closing = true
        this.opts.handlers.onConnection?.('ended')
        this.opts.handlers.onEnded?.()
        return
      }
      this.reconnect()
    }
  }

  private reconnect(): void {
    if (this.closing) return
    this.ws?.close()
    this.ws = null
    this.opts.handlers.onConnection?.('reconnecting')
    // The model was mid-sentence; its buffered tail is stale now.
    this.player?.port.postMessage({ type: 'flush' })
    const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** this.retries++)
    setTimeout(() => {
      if (!this.closing) this.connect()
    }, delay)
  }

  private sendBinary(pcm: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(pcm)
  }

  /** Peak levels in 0–1, for the waveform and the avatar rings. */
  levels(): { input: number; output: number } {
    return { input: peak(this.inAnalyser, this.inBuf), output: peak(this.outAnalyser, this.outBuf) }
  }

  async stop(): Promise<void> {
    this.closing = true
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: 'end' }))
    this.ws?.close()
    this.ws = null
    this.recorder?.disconnect()
    this.player?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    await Promise.allSettled([this.inCtx?.close(), this.outCtx?.close()])
    this.inCtx = this.outCtx = null
    this.opts.handlers.onConnection?.('ended')
  }
}

function peak(analyser: AnalyserNode | null, buf: Uint8Array): number {
  if (!analyser) return 0
  analyser.getByteFrequencyData(buf as Uint8Array<ArrayBuffer>)
  let max = 0
  for (let i = 0; i < buf.length; i++) if (buf[i] > max) max = buf[i]
  return max / 255
}
