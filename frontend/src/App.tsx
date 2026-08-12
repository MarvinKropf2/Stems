import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { fetchJobs, uploadFiles } from './api'
import { Dropzone } from './components/Dropzone'
import { SongCard } from './components/SongCard'
import type { Job } from './types'

function App() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const latest = await fetchJobs()
      setJobs(latest.slice().reverse()) // newest first
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  // Poll while any job is still working.
  useEffect(() => {
    refresh()
    pollRef.current = window.setInterval(() => {
      setJobs((cur) => {
        const active = cur.some(
          (j) => j.status === 'queued' || j.status === 'processing',
        )
        if (active) refresh()
        return cur
      })
    }, 2000)
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [refresh])

  async function onFiles(files: File[]) {
    setError(null)
    try {
      await uploadFiles(files)
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span className="mark">/</span>stems
        </h1>
        <span className="tagline">offline stem separation · demucs</span>
      </header>

      <Dropzone onFiles={onFiles} />

      {error && <p className="banner error">{error}</p>}

      <div className="jobs">
        {jobs.length === 0 && (
          <p className="empty">No songs yet — drop some in above.</p>
        )}
        {jobs.map((job) => (
          <SongCard key={job.id} job={job} />
        ))}
      </div>
    </div>
  )
}

export default App
