import { useState, useCallback, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import FileDropzone from '../components/FileDropzone'
import './OcrPage.css'

type JobStatus = 'queued' | 'uploading' | 'processing' | 'completed' | 'error'

interface OcrJob {
  id: string
  file: File
  previewUrl: string | null
  status: JobStatus
  uploadProgress: number
  processingProgress: number
  progressStage: string
  content: string
  pageCount: number
  error: string
  fileId: string | null
}

interface HistoryDoc {
  file_id: string
  status: string
  total_page_count: number | null
  created_at: string | null
  has_content: boolean
}

let jobCounter = 0

function createJob(file: File): OcrJob {
  const isImage = file.type.startsWith('image/')
  return {
    id: `job-${++jobCounter}`,
    file,
    previewUrl: isImage ? URL.createObjectURL(file) : null,
    status: 'queued',
    uploadProgress: 0,
    processingProgress: 0,
    progressStage: '',
    content: '',
    pageCount: 0,
    error: '',
    fileId: null,
  }
}

export default function OcrPage() {
  const [jobs, setJobs] = useState<OcrJob[]>([])
  const [history, setHistory] = useState<HistoryDoc[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [expandedHistoryIds, setExpandedHistoryIds] = useState<string[]>([])
  const [historyDetails, setHistoryDetails] = useState<Record<string, { loading?: boolean; error?: string; content?: string }>>({})
  const pollingRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/documents/?limit=20')
      if (res.ok) {
        setHistory(await res.json())
      }
    } catch { /* ignore */ }
    finally { setHistoryLoading(false) }
  }, [])

  useEffect(() => { fetchHistory() }, [fetchHistory])

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
            processingProgress: 100,
            progressStage: '',
          })
          fetchHistory()
        } else if (data.status === 'error') {
          clearInterval(interval)
          pollingRefs.current.delete(jobId)
          updateJob(jobId, {
            status: 'error',
            error: data.error_message || 'Xatolik yuz berdi',
          })
        } else {
          // Still processing — update progress
          updateJob(jobId, {
            processingProgress: data.progress ?? 0,
            progressStage: data.progress_stage ?? 'Ishlanmoqda...',
          })
        }
      } catch {
        clearInterval(interval)
        pollingRefs.current.delete(jobId)
        updateJob(jobId, { status: 'error', error: "Serverga ulanib bo'lmadi" })
      }
    }, 2000)
    pollingRefs.current.set(jobId, interval)
  }, [updateJob, fetchHistory])

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
        updateJob(job.id, { status: 'processing', fileId: data.file_id, processingProgress: 0, progressStage: 'Navbatda...' })
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
    setJobs(prev => {
      const job = prev.find(j => j.id === id)
      if (job?.previewUrl) URL.revokeObjectURL(job.previewUrl)
      return prev.filter(j => j.id !== id)
    })
  }, [])

  const loadHistoryDetail = useCallback(async (fileId: string) => {
    setHistoryDetails(prev => ({ ...prev, [fileId]: { ...prev[fileId], loading: true, error: '' } }))
    try {
      const res = await fetch(`/api/status/${fileId}`)
      if (!res.ok) throw new Error(`Server xatosi: ${res.status}`)
      const data = await res.json()
      setHistoryDetails(prev => ({ ...prev, [fileId]: { loading: false, error: '', content: data.content || '' } }))
    } catch (error) {
      setHistoryDetails(prev => ({
        ...prev,
        [fileId]: { ...prev[fileId], loading: false, error: error instanceof Error ? error.message : "Ma'lumotni olib bo'lmadi" },
      }))
    }
  }, [])

  const toggleHistoryItem = useCallback((fileId: string) => {
    setExpandedHistoryIds(prev => {
      const isOpen = prev.includes(fileId)
      if (isOpen) return prev.filter(id => id !== fileId)
      return [...prev, fileId]
    })
    const detail = historyDetails[fileId]
    if (!detail || (!detail.loading && !detail.content)) {
      loadHistoryDetail(fileId)
    }
  }, [historyDetails, loadHistoryDetail])

  const deleteHistoryItem = useCallback(async (fileId: string) => {
    try {
      const res = await fetch(`/api/documents/${fileId}`, { method: 'DELETE' })
      if (res.ok) {
        setHistory(prev => prev.filter(d => d.file_id !== fileId))
      }
    } catch { /* ignore */ }
    finally { setDeleteConfirmId(null) }
  }, [])

  const hasJobs = jobs.length > 0

  return (
    <div className="ocr">
      <nav className="ocr-nav">
        <Link to="/" className="back-link">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m15 18-6-6 6-6" />
          </svg>
          Bosh sahifa
        </Link>
        <h1 className="ocr-nav-title">Rasmdan matn AI</h1>
        <div className="nav-links">
          <Link to="/letters" className="nav-link">
            Hatlar AI
          </Link>
          <Link to="/meeting" className="nav-link">
            Majlis stenografiyasi
          </Link>
        </div>
      </nav>

      <main className="ocr-main-multi">
        <FileDropzone onFilesSelected={addFiles} />

        {hasJobs && (
          <div className="jobs-list">
            {jobs.map((job) => (
              <div className={`job-card job-${job.status}`} key={job.id}>
                <div className="job-header">
                  <div className="job-file-info">
                    {job.previewUrl ? (
                      <img className="job-thumb" src={job.previewUrl} alt="" />
                    ) : (
                      <div className="job-thumb job-thumb-pdf">PDF</div>
                    )}
                    <div>
                      <span className="job-file-name">{job.file.name}</span>
                      <span className="job-file-size">
                        {(job.file.size / 1024).toFixed(0)} KB
                      </span>
                    </div>
                  </div>
                  <div className="job-actions">
                    <StatusBadge status={job.status} />
                    <button
                      className="job-remove"
                      onClick={() => removeJob(job.id)}
                      title="Olib tashlash"
                    >
                      &times;
                    </button>
                  </div>
                </div>

                {job.status === "uploading" && (
                  <div className="job-progress">
                    <div className="progress-bar-container">
                      <div
                        className="progress-bar"
                        style={{ width: `${job.uploadProgress}%` }}
                      />
                    </div>
                    <span className="progress-label">
                      {job.uploadProgress}%
                    </span>
                  </div>
                )}

                {job.status === "processing" && (
                  <div className="job-progress">
                    <div className="progress-bar-container">
                      <div
                        className="progress-bar progress-bar-processing"
                        style={{ width: `${job.processingProgress}%` }}
                      />
                    </div>
                    <span className="progress-label">
                      {job.processingProgress}%
                    </span>
                    <span className="progress-stage">{job.progressStage}</span>
                  </div>
                )}

                {job.status === "error" && (
                  <div className="job-error">
                    <p>{job.error}</p>
                    <button
                      className="retry-btn-sm"
                      onClick={() => retryJob(job)}
                    >
                      Qayta urinish
                    </button>
                  </div>
                )}

                {job.status === "completed" && (
                  <div className="job-result">
                    {job.pageCount > 0 && (
                      <span className="page-badge">{job.pageCount} sahifa</span>
                    )}
                    {job.fileId && (
                      <div className="file-preview-toggle">
                        <a
                          href={`/api/file/${job.fileId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="preview-link"
                        >
                          Asl hujjatni ko'rish
                        </a>
                      </div>
                    )}
                    <pre className="result-content">{job.content}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!historyLoading && history.length > 0 && (
          <div className="history-section">
            <h2 className="history-heading">Oxirgi hujjatlar</h2>
            <div className="history-list">
              {history.map((doc) => (
                <div
                  className={`history-item history-${doc.status}`}
                  key={doc.file_id}
                >
                  <button
                    className="history-toggle"
                    onClick={() => toggleHistoryItem(doc.file_id)}
                    type="button"
                  >
                    <div className="history-info">
                      <svg
                        className="history-icon"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                        <path d="M14 2v6h6" />
                      </svg>
                      <div>
                        <span className="history-id">
                          {doc.file_id.slice(0, 8)}...
                        </span>
                        {doc.created_at && (
                          <span className="history-date">
                            {new Date(doc.created_at).toLocaleString("uz-UZ")}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="history-meta">
                      {doc.total_page_count && doc.total_page_count > 0 && (
                        <span className="page-badge">
                          {doc.total_page_count} sahifa
                        </span>
                      )}
                      <HistoryStatusBadge status={doc.status} />
                      <svg
                        className={`history-chevron ${expandedHistoryIds.includes(doc.file_id) ? "expanded" : ""}`}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        width="18"
                        height="18"
                      >
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                      <button
                        className="history-delete-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteConfirmId(doc.file_id);
                        }}
                        title="O'chirish"
                        type="button"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          width="16"
                          height="16"
                        >
                          <path d="M3 6h18" />
                          <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                        </svg>
                      </button>
                    </div>
                  </button>

                  {expandedHistoryIds.includes(doc.file_id) && (
                    <div className="history-detail">
                      {historyDetails[doc.file_id]?.loading && (
                        <div className="job-processing">
                          <div className="spinner-sm" />
                          <span>Ma'lumot yuklanmoqda...</span>
                        </div>
                      )}
                      {historyDetails[doc.file_id]?.error && (
                        <div className="job-error">
                          <p>{historyDetails[doc.file_id]?.error}</p>
                        </div>
                      )}
                      {!historyDetails[doc.file_id]?.loading &&
                        !historyDetails[doc.file_id]?.error &&
                        historyDetails[doc.file_id]?.content && (
                          <pre className="result-content">
                            {historyDetails[doc.file_id]?.content}
                          </pre>
                        )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {deleteConfirmId && (
        <div
          className="preview-modal-overlay"
          onClick={() => setDeleteConfirmId(null)}
        >
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Hujjatni o'chirish</h3>
            <p>Haqiqatan ham bu hujjatni o'chirmoqchimisiz?</p>
            <div className="confirm-actions">
              <button
                className="confirm-cancel"
                onClick={() => setDeleteConfirmId(null)}
                type="button"
              >
                Bekor qilish
              </button>
              <button
                className="confirm-delete"
                onClick={() => deleteHistoryItem(deleteConfirmId)}
                type="button"
              >
                O'chirish
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
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

function HistoryStatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    processing: 'Ishlanmoqda',
    completed: 'Tayyor',
    failed: 'Xatolik',
  }
  const css: Record<string, string> = {
    processing: 'status-processing',
    completed: 'status-completed',
    failed: 'status-error',
  }
  return <span className={`status-badge ${css[status] || 'status-queued'}`}>{labels[status] || status}</span>
}
