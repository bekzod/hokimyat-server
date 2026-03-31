import { useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import FileDropzone from '../components/FileDropzone'
import './OcrPage.css'

type JobStatus = 'queued' | 'uploading' | 'processing' | 'completed' | 'error'

interface OcrJob {
  id: string
  file: File
  status: JobStatus
  uploadProgress: number
  content: string
  pageCount: number
  error: string
  fileId: string | null
}

let jobCounter = 0

function createJob(file: File): OcrJob {
  return {
    id: `job-${++jobCounter}`,
    file,
    status: 'queued',
    uploadProgress: 0,
    content: '',
    pageCount: 0,
    error: '',
    fileId: null,
  }
}

export default function OcrPage() {
  const [jobs, setJobs] = useState<OcrJob[]>([])
  const pollingRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  const updateJob = useCallback((id: string, patch: Partial<OcrJob>) => {
    setJobs(prev => prev.map(j => (j.id === id ? { ...j, ...patch } : j)))
  }, [])

  const pollStatus = useCallback((jobId: string, fileId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${fileId}`)
        if (!res.ok) throw new Error('Status check failed')
        const data = await res.json()

        if (data.status === 'completed') {
          clearInterval(interval)
          pollingRefs.current.delete(jobId)
          updateJob(jobId, {
            status: 'completed',
            content: data.content || '',
            pageCount: data.total_page_count || 0,
          })
        } else if (data.status === 'error') {
          clearInterval(interval)
          pollingRefs.current.delete(jobId)
          updateJob(jobId, {
            status: 'error',
            error: data.error_message || 'Xatolik yuz berdi',
          })
        }
      } catch {
        clearInterval(interval)
        pollingRefs.current.delete(jobId)
        updateJob(jobId, { status: 'error', error: "Serverga ulanib bo'lmadi" })
      }
    }, 2000)
    pollingRefs.current.set(jobId, interval)
  }, [updateJob])

  const uploadOne = useCallback((job: OcrJob) => {
    updateJob(job.id, { status: 'uploading', uploadProgress: 0 })

    const form = new FormData()
    form.append('file', job.file)
    form.append('tasks', 'ocr_only')

    const xhr = new XMLHttpRequest()
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        updateJob(job.id, { uploadProgress: Math.round((e.loaded / e.total) * 100) })
      }
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const data = JSON.parse(xhr.responseText)
        updateJob(job.id, { status: 'processing', fileId: data.file_id })
        pollStatus(job.id, data.file_id)
      } else {
        let msg = `Server xatosi: ${xhr.status}`
        try { msg = JSON.parse(xhr.responseText).detail || msg } catch { /* */ }
        updateJob(job.id, { status: 'error', error: msg })
      }
    })
    xhr.addEventListener('error', () => {
      updateJob(job.id, { status: 'error', error: 'Tarmoq xatosi' })
    })
    xhr.open('POST', '/api/upload-document/')
    xhr.send(form)
  }, [updateJob, pollStatus])

  const addFiles = useCallback((files: File[]) => {
    const newJobs = files.map(createJob)
    setJobs(prev => [...prev, ...newJobs])
    newJobs.forEach(uploadOne)
  }, [uploadOne])

  const retryJob = useCallback((job: OcrJob) => {
    uploadOne(job)
  }, [uploadOne])

  const removeJob = useCallback((id: string) => {
    const interval = pollingRefs.current.get(id)
    if (interval) {
      clearInterval(interval)
      pollingRefs.current.delete(id)
    }
    setJobs(prev => prev.filter(j => j.id !== id))
  }, [])

  const hasJobs = jobs.length > 0

  return (
    <div className="ocr">
      <nav className="ocr-nav">
        <Link to="/" className="back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
          Bosh sahifa
        </Link>
        <h1 className="ocr-nav-title">Rasmdan matn AI</h1>
        <div style={{ width: 120 }} />
      </nav>

      <main className="ocr-main-multi">
        <FileDropzone onFilesSelected={addFiles} />

        {hasJobs && (
          <div className="jobs-list">
            {jobs.map(job => (
              <div className={`job-card job-${job.status}`} key={job.id}>
                <div className="job-header">
                  <div className="job-file-info">
                    <svg className="job-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                      <path d="M14 2v6h6" />
                    </svg>
                    <div>
                      <span className="job-file-name">{job.file.name}</span>
                      <span className="job-file-size">{(job.file.size / 1024).toFixed(0)} KB</span>
                    </div>
                  </div>
                  <div className="job-actions">
                    <StatusBadge status={job.status} />
                    <button className="job-remove" onClick={() => removeJob(job.id)} title="Olib tashlash">
                      &times;
                    </button>
                  </div>
                </div>

                {job.status === 'uploading' && (
                  <div className="job-progress">
                    <div className="progress-bar-container">
                      <div className="progress-bar" style={{ width: `${job.uploadProgress}%` }} />
                    </div>
                    <span className="progress-label">{job.uploadProgress}%</span>
                  </div>
                )}

                {job.status === 'processing' && (
                  <div className="job-processing">
                    <div className="spinner-sm" />
                    <span>Matn ajratilmoqda...</span>
                  </div>
                )}

                {job.status === 'error' && (
                  <div className="job-error">
                    <p>{job.error}</p>
                    <button className="retry-btn-sm" onClick={() => retryJob(job)}>Qayta urinish</button>
                  </div>
                )}

                {job.status === 'completed' && (
                  <div className="job-result">
                    {job.pageCount > 0 && <span className="page-badge">{job.pageCount} sahifa</span>}
                    <pre className="result-content">{job.content}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function StatusBadge({ status }: { status: JobStatus }) {
  const labels: Record<JobStatus, string> = {
    queued: 'Navbatda',
    uploading: 'Yuklanmoqda',
    processing: 'Ishlanmoqda',
    completed: 'Tayyor',
    error: 'Xatolik',
  }
  return <span className={`status-badge status-${status}`}>{labels[status]}</span>
}
