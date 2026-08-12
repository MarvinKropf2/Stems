import { useState } from 'react'
import { downloadUrl } from '../api'
import { STEMS, type Format, type Job } from '../types'

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
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [format, setFormat] = useState<Format>('wav')

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const isDone = job.status === 'done'

  return (
    <div className={`card status-${job.status}`}>
      <div className="card-head">
        <span className="card-name" title={job.filename}>
          {job.filename}
        </span>
        <span className={`badge badge-${job.status}`}>
          {job.status !== 'done' && job.status !== 'error' && <span className="spinner" />}
          {STATUS_LABEL[job.status]}
        </span>
      </div>

      {job.status === 'error' && <p className="card-error">{job.error}</p>}

      {isDone && (
        <>
          <div className="stem-grid">
            {STEMS.map(({ key, label }) => (
              <label key={key} className={`stem-chip${selected.has(key) ? ' on' : ''}`}>
                <input
                  type="checkbox"
                  checked={selected.has(key)}
                  onChange={() => toggle(key)}
                />
                {label}
              </label>
            ))}
          </div>

          <div className="card-controls">
            <div className="format-toggle">
              {(['wav', 'mp3'] as Format[]).map((f) => (
                <button
                  key={f}
                  className={format === f ? 'on' : ''}
                  onClick={() => setFormat(f)}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>

            <button
              className="btn primary"
              disabled={selected.size === 0}
              onClick={() =>
                triggerDownload(downloadUrl(job.id, [...selected], format))
              }
            >
              Download selected{selected.size ? ` (${selected.size})` : ''}
            </button>
          </div>

          <div className="quick-row">
            <span className="quick-label">Quick:</span>
            <button
              className="btn ghost"
              onClick={() =>
                triggerDownload(downloadUrl(job.id, ['drums', 'bass', 'other'], format))
              }
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
