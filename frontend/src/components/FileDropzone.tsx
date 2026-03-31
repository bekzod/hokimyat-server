import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

interface FileDropzoneProps {
  onFilesSelected: (files: File[]) => void
  accept?: Record<string, string[]>
  hint?: string
}

const DEFAULT_ACCEPT = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/tiff': ['.tiff'],
  'image/bmp': ['.bmp'],
}

export default function FileDropzone({ onFilesSelected, accept, hint }: FileDropzoneProps) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) onFilesSelected(accepted)
    },
    [onFilesSelected],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: accept || DEFAULT_ACCEPT,
    multiple: true,
  })

  return (
    <div
      {...getRootProps()}
      className={`drop-zone ${isDragActive ? 'drag-over' : ''}`}
    >
      <input {...getInputProps()} />
      <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <p className="drop-text">Fayllarni bu yerga tashlang yoki bosing</p>
      <p className="drop-hint">{hint || 'PDF, PNG, JPG, TIFF — bir nechta fayl tanlash mumkin'}</p>
    </div>
  )
}
