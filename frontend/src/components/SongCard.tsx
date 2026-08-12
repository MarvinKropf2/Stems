import { useCallback, useState } from 'react'
import { downloadUrl } from '../api'
import { STEMS, type Format, type Job } from '../types'
import { StemPlayer } from './StemPlayer'

function triggerDownload(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

const STATUS_LABEL: Record<Job['status'], string> = {
  queued: 'Queued…',
  processing: 'Separating stems…',
  done: 'Done',
  error: 'Error',
}

export function SongCard({ job }: { job: Job }) {
  const [format, setFormat] = useState<Format>('wav')
  // Stems currently audible in the mixer — this is what "Download" grabs.
  const [audible, setAudible] = useState<string[]>(STEMS.map((s) => s.key))

  const onAudibleChange = useCallback((stems: string[]) => setAudible(stems), [])

  const isDone = job.status === 'done'

  return (
    <div className={`card status-${job.status}`}>
      <div className="card-head">
        <span className="card-name" title={job.filename}>
          {job.filename}
        </span>
        <span className="head-right">
          {isDone && job.bpm != null && <span className="meta-badge">{job.bpm} BPM</span>}
          {isDone && job.key && (
            <span className="meta-badge key" title={job.key_musical ?? undefined}>
              {job.key}
            </span>
          )}
          <span className={`badge badge-${job.status}`}>
            {job.status !== 'done' && job.status !== 'error' && <span className="spinner" />}
            {STATUS_LABEL[job.status]}
          </span>
        </span>
      </div>

      {job.status === 'error' && <p className="card-error">{job.error}</p>}

      {isDone && (
        <>
          <StemPlayer jobId={job.id} onAudibleChange={onAudibleChange} />

          <div className="card-controls">
            <div className="format-toggle">
              {(['wav', 'mp3'] as Format[]).map((f) => (
                <button key={f} className={format === f ? 'on' : ''} onClick={() => setFormat(f)}>
                  {f.toUpperCase()}
                </button>
              ))}
            </div>

            <button
              className="btn primary"
              disabled={audible.length === 0}
              onClick={() => triggerDownload(downloadUrl(job.id, audible, format))}
            >
              Download what I'm hearing{audible.length ? ` (${audible.length})` : ''}
            </button>
          </div>

          <p className="format-hint">
            {format === 'wav'
              ? 'WAV: lossless, keeps text tags (BPM/key/title) — no cover art.'
              : 'MP3 320k: full tags + embedded cover art.'}
          </p>

          <div className="quick-row">
            <span className="quick-label">Quick:</span>
            <button
              className="btn ghost"
              onClick={() => triggerDownload(downloadUrl(job.id, ['drums', 'bass', 'other'], format))}
            >
              Instrumental
            </button>
            <button
              className="btn ghost"
              onClick={() => triggerDownload(downloadUrl(job.id, ['vocals'], format))}
            >
              Acapella
            </button>
            {STEMS.map(({ key, label }) => (
              <button
                key={key}
                className="btn ghost"
                onClick={() => triggerDownload(downloadUrl(job.id, [key], format))}
              >
                {label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
