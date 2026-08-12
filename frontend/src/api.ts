import type { Job } from './types'

export async function uploadFiles(files: File[]): Promise<Job[]> {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const res = await fetch('/api/upload', { method: 'POST', body: form })
  if (!res.ok) throw new Error(`upload failed: ${res.status}`)
  return res.json()
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch('/api/jobs')
  if (!res.ok) throw new Error(`fetch jobs failed: ${res.status}`)
  return res.json()
}

/** URL for streaming a single raw stem (used by the preview mixer). */
export function stemUrl(jobId: string, name: string): string {
  return `/api/jobs/${jobId}/stem/${name}`
}

/** URL for downloading a combined file of the chosen stems. */
export function downloadUrl(
  jobId: string,
  stems: string[],
  format: string,
): string {
  const q = new URLSearchParams({ stems: stems.join(','), format })
  return `/api/jobs/${jobId}/download?${q.toString()}`
}
