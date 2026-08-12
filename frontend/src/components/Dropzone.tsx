import { useRef, useState } from 'react'

interface Props {
  onFiles: (files: File[]) => void
  disabled?: boolean
}

const AUDIO_RE = /\.(mp3|wav|flac|m4a|aac|ogg|aiff?|wma)$/i

export function Dropzone({ onFiles, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleFiles(list: FileList | null) {
    if (!list) return
    const files = Array.from(list).filter((f) => AUDIO_RE.test(f.name))
    if (files.length) onFiles(files)
  }

  return (
    <div
      className={`dropzone${dragging ? ' dragging' : ''}${disabled ? ' disabled' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        if (!disabled) handleFiles(e.dataTransfer.files)
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="audio/*"
        hidden
        onChange={(e) => {
          handleFiles(e.target.files)
          e.target.value = ''
        }}
      />
      <div className="dropzone-inner">
        <div className="dropzone-icon" aria-hidden="true">
          <i /><i /><i /><i /><i />
        </div>
        <p className="dropzone-title">Drop songs here</p>
        <p className="dropzone-sub">or click to browse — MP3, WAV, FLAC, M4A · multiple at once</p>
      </div>
    </div>
  )
}
