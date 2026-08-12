export type JobStatus = 'queued' | 'processing' | 'done' | 'error'

export interface Job {
  id: string
  filename: string
  status: JobStatus
  error: string | null
  stems: string[]
  bpm: number | null
  key: string | null // Camelot, e.g. "8A"
  key_musical: string | null // e.g. "Am"
}

export type Format = 'wav' | 'mp3'

// The four stems Demucs (htdemucs) produces, with display labels.
export const STEMS: { key: string; label: string }[] = [
  { key: 'vocals', label: 'Acapella' },
  { key: 'drums', label: 'Drums' },
  { key: 'bass', label: 'Bass' },
  { key: 'other', label: 'Melody' },
]
