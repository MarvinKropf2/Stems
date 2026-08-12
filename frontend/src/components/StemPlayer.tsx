import { useCallback, useEffect, useRef, useState } from 'react'
import { stemUrl } from '../api'
import { STEMS } from '../types'

interface Props {
  jobId: string
  /** Called whenever the set of audible stems changes (drives the download). */
  onAudibleChange: (stems: string[]) => void
}

function fmtTime(s: number): string {
  if (!isFinite(s)) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

/**
 * Plays all 4 stems sample-synced via the Web Audio API, with per-stem mute/solo.
 * Web Audio buffer sources are one-shot, so play/pause/seek recreate them at an
 * offset; mute/solo just adjust persistent gain nodes (no restart needed).
 */
export function StemPlayer({ jobId, onAudibleChange }: Props) {
  const ctxRef = useRef<AudioContext | null>(null)
  const buffersRef = useRef<Record<string, AudioBuffer>>({})
  const gainsRef = useRef<Record<string, GainNode>>({})
  const sourcesRef = useRef<AudioBufferSourceNode[]>([])
  const startedAtRef = useRef(0) // ctx time when current playback began
  const offsetRef = useRef(0) // playback position at last pause/seek
  const rafRef = useRef<number | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [muted, setMuted] = useState<Set<string>>(new Set())
  const [soloed, setSoloed] = useState<Set<string>>(new Set())

  // Which stems are currently audible, given mute/solo state.
  const audibleStems = useCallback((): string[] => {
    const names = STEMS.map((s) => s.key)
    if (soloed.size > 0) return names.filter((n) => soloed.has(n))
    return names.filter((n) => !muted.has(n))
  }, [muted, soloed])

  // Load + decode all stems once.
  useEffect(() => {
    let cancelled = false
    const ctx = new AudioContext()
    ctxRef.current = ctx
    ;(async () => {
      try {
        const entries = await Promise.all(
          STEMS.map(async ({ key }) => {
            const res = await fetch(stemUrl(jobId, key))
            if (!res.ok) throw new Error(`stem ${key}: ${res.status}`)
            const buf = await ctx.decodeAudioData(await res.arrayBuffer())
            return [key, buf] as const
          }),
        )
        if (cancelled) return
        let dur = 0
        for (const [key, buf] of entries) {
          buffersRef.current[key] = buf
          const g = ctx.createGain()
          g.connect(ctx.destination)
          gainsRef.current[key] = g
          dur = Math.max(dur, buf.duration)
        }
        setDuration(dur)
        setLoading(false)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    })()

    return () => {
      cancelled = true
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      sourcesRef.current.forEach((s) => {
        try {
          s.stop()
        } catch {
          /* already stopped */
        }
      })
      ctx.close()
    }
  }, [jobId])

  // Apply mute/solo to gains live, and report the audible set upward.
  useEffect(() => {
    const audible = new Set(audibleStems())
    for (const { key } of STEMS) {
      const g = gainsRef.current[key]
      if (g) g.gain.value = audible.has(key) ? 1 : 0
    }
    onAudibleChange([...audible])
  }, [muted, soloed, audibleStems, onAudibleChange, loading])

  const tick = useCallback(() => {
    const ctx = ctxRef.current
    if (!ctx) return
    const pos = offsetRef.current + (ctx.currentTime - startedAtRef.current)
    if (pos >= duration) {
      // reached the end
      setPlaying(false)
      setPosition(duration)
      offsetRef.current = 0
      sourcesRef.current.forEach((s) => {
        try {
          s.stop()
        } catch {
          /* noop */
        }
      })
      sourcesRef.current = []
      return
    }
    setPosition(pos)
    rafRef.current = requestAnimationFrame(tick)
  }, [duration])

  const startPlayback = useCallback(
    async (from: number) => {
      const ctx = ctxRef.current
      if (!ctx) return
      await ctx.resume()
      // (re)create one source per stem, all started together at `from`.
      const sources: AudioBufferSourceNode[] = []
      for (const { key } of STEMS) {
        const buf = buffersRef.current[key]
        if (!buf) continue
        const src = ctx.createBufferSource()
        src.buffer = buf
        src.connect(gainsRef.current[key])
        src.start(0, from)
        sources.push(src)
      }
      sourcesRef.current = sources
      startedAtRef.current = ctx.currentTime
      offsetRef.current = from
      setPlaying(true)
      rafRef.current = requestAnimationFrame(tick)
    },
    [tick],
  )

  const stopPlayback = useCallback(() => {
    const ctx = ctxRef.current
    if (ctx) offsetRef.current += ctx.currentTime - startedAtRef.current
    sourcesRef.current.forEach((s) => {
      try {
        s.stop()
      } catch {
        /* noop */
      }
    })
    sourcesRef.current = []
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    setPlaying(false)
  }, [])

  function togglePlay() {
    if (playing) stopPlayback()
    else startPlayback(offsetRef.current >= duration ? 0 : offsetRef.current)
  }

  function seek(to: number) {
    const wasPlaying = playing
    if (wasPlaying) stopPlayback()
    offsetRef.current = to
    setPosition(to)
    if (wasPlaying) startPlayback(to)
  }

  function toggleMute(key: string) {
    setMuted((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function toggleSolo(key: string) {
    setSoloed((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  // "Instrumental" = the drums + bass + melody group, controlled together.
  const INSTRUMENTAL = ['drums', 'bass', 'other']
  const instrMuted = INSTRUMENTAL.every((k) => muted.has(k))
  const instrSoloed =
    soloed.size === INSTRUMENTAL.length && INSTRUMENTAL.every((k) => soloed.has(k))

  function toggleInstrMute() {
    setMuted((prev) => {
      const next = new Set(prev)
      if (INSTRUMENTAL.every((k) => next.has(k))) INSTRUMENTAL.forEach((k) => next.delete(k))
      else INSTRUMENTAL.forEach((k) => next.add(k))
      return next
    })
  }

  function toggleInstrSolo() {
    // Solo the whole group, or clear if it's already the soloed set.
    setSoloed(() => (instrSoloed ? new Set() : new Set(INSTRUMENTAL)))
  }

  if (error) return <p className="card-error">Preview error: {error}</p>
  if (loading) return <p className="player-loading">Loading preview…</p>

  const audible = new Set(audibleStems())
  const instrAudible = INSTRUMENTAL.every((k) => audible.has(k))

  return (
    <div className="player">
      <div className="transport">
        <button className="play-btn" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '⏸' : '▶'}
        </button>
        <span className="time">{fmtTime(position)}</span>
        <input
          className="seek"
          type="range"
          min={0}
          max={duration || 0}
          step={0.01}
          value={position}
          onChange={(e) => seek(Number(e.target.value))}
        />
        <span className="time">{fmtTime(duration)}</span>
      </div>

      <div className="mixer">
        {STEMS.map(({ key, label }) => {
          const on = audible.has(key)
          return (
            <div key={key} className={`mix-row${on ? '' : ' off'}`}>
              <span className="mix-name">{label}</span>
              <button
                className={`mix-btn${muted.has(key) ? ' active' : ''}`}
                onClick={() => toggleMute(key)}
                title="Mute"
              >
                M
              </button>
              <button
                className={`mix-btn solo${soloed.has(key) ? ' active' : ''}`}
                onClick={() => toggleSolo(key)}
                title="Solo"
              >
                S
              </button>
            </div>
          )
        })}

        {/* Group control for the instrumental = drums + bass + melody together. */}
        <div className={`mix-row mix-group${instrAudible ? '' : ' off'}`}>
          <span className="mix-name">
            Instrumental <span className="mix-sub">drums + bass + melody</span>
          </span>
          <button
            className={`mix-btn${instrMuted ? ' active' : ''}`}
            onClick={toggleInstrMute}
            title="Mute drums + bass + melody"
          >
            M
          </button>
          <button
            className={`mix-btn solo${instrSoloed ? ' active' : ''}`}
            onClick={toggleInstrSolo}
            title="Solo drums + bass + melody (vocals off)"
          >
            S
          </button>
        </div>
      </div>
    </div>
  )
}
