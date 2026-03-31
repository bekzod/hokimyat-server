import { useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import FileDropzone from '../components/FileDropzone'
import './LettersPage.css'

type JobStatus = 'queued' | 'uploading' | 'processing' | 'completed' | 'error'
type InputMode = 'file' | 'text'

interface AuthorInfo {
  last_name?: string
  first_name?: string
  middle_name?: string
  date_of_birth?: string
  gender?: string
  phones?: string[]
  email?: string
  country?: string
  city?: string
  region?: string
  district?: string
  address?: string
  date_of_issue?: string
  date_when_document_was_written?: string
}

interface Department {
  order?: number
  id?: string
  reasoning?: string
  full_name?: string
  position?: string
  responsibilities?: string[]
}

interface Issues {
  issues?: string[]
  keywords?: string[]
}

interface AnalysisResult {
  summary?: string
  author_info?: AuthorInfo
  department?: Department
  issues?: Issues
  entity?: { entity_type?: string }
  is_repeated?: boolean
  repeated_dates?: string[]
}

interface LetterJob {
  id: string
  fileName: string
  fileSize: number
  status: JobStatus
  uploadProgress: number
  result: AnalysisResult | null
  error: string
}

let jobCounter = 0

export default function LettersPage() {
  const [inputMode, setInputMode] = useState<InputMode>('file')
  const [jobs, setJobs] = useState<LetterJob[]>([])
  const [rawText, setRawText] = useState('')
  const [textStatus, setTextStatus] = useState<'idle' | 'processing' | 'completed' | 'error'>('idle')
  const [textResult, setTextResult] = useState<AnalysisResult | null>(null)
  const [textError, setTextError] = useState('')
  const pollingRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  const updateJob = useCallback((id: string, patch: Partial<LetterJob>) => {
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
          updateJob(jobId, { status: 'completed', result: data.meta || {} })
        } else if (data.status === 'error') {
          clearInterval(interval)
          pollingRefs.current.delete(jobId)
          updateJob(jobId, { status: 'error', error: data.error_message || 'Xatolik yuz berdi' })
        }
      } catch {
        clearInterval(interval)
        pollingRefs.current.delete(jobId)
        updateJob(jobId, { status: 'error', error: "Serverga ulanib bo'lmadi" })
      }
    }, 2000)
    pollingRefs.current.set(jobId, interval)
  }, [updateJob])

  const uploadOne = useCallback((job: LetterJob, file: File) => {
    updateJob(job.id, { status: 'uploading', uploadProgress: 0 })

    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        updateJob(job.id, { uploadProgress: Math.round((e.loaded / e.total) * 100) })
      }
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const data = JSON.parse(xhr.responseText)
        updateJob(job.id, { status: 'processing' })
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
    const newJobs: LetterJob[] = files.map(f => ({
      id: `lj-${++jobCounter}`,
      fileName: f.name,
      fileSize: f.size,
      status: 'queued',
      uploadProgress: 0,
      result: null,
      error: '',
    }))
    setJobs(prev => [...prev, ...newJobs])
    files.forEach((f, i) => uploadOne(newJobs[i], f))
  }, [uploadOne])

  const removeJob = useCallback((id: string) => {
    const interval = pollingRefs.current.get(id)
    if (interval) {
      clearInterval(interval)
      pollingRefs.current.delete(id)
    }
    setJobs(prev => prev.filter(j => j.id !== id))
  }, [])

  const analyzeText = async () => {
    if (!rawText.trim()) return
    setTextStatus('processing')
    setTextError('')

    try {
      const res = await fetch('/api/analyze-text/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: rawText }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail || `Server xatosi: ${res.status}`)
      }
      const data = await res.json()
      setTextResult(data.meta || {})
      setTextStatus('completed')
    } catch (e) {
      setTextError(e instanceof Error ? e.message : 'Xatolik yuz berdi')
      setTextStatus('error')
    }
  }

  const resetText = () => {
    setRawText('')
    setTextStatus('idle')
    setTextResult(null)
    setTextError('')
  }

  return (
    <div className="letters">
      <nav className="ocr-nav">
        <Link to="/" className="back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
          Bosh sahifa
        </Link>
        <h1 className="ocr-nav-title">Hatlar AI</h1>
        <div style={{ width: 120 }} />
      </nav>

      <main className="ocr-main-multi">
        <div className="mode-toggle">
          <button
            className={`mode-btn ${inputMode === 'file' ? 'active' : ''}`}
            onClick={() => setInputMode('file')}
          >
            Fayl yuklash
          </button>
          <button
            className={`mode-btn ${inputMode === 'text' ? 'active' : ''}`}
            onClick={() => setInputMode('text')}
          >
            Matn kiritish
          </button>
        </div>

        {inputMode === 'file' && (
          <>
            <FileDropzone onFilesSelected={addFiles} />

            {jobs.length > 0 && (
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
                          <span className="job-file-name">{job.fileName}</span>
                          <span className="job-file-size">{(job.fileSize / 1024).toFixed(0)} KB</span>
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
                        <span>Tahlil qilinmoqda...</span>
                      </div>
                    )}

                    {job.status === 'error' && (
                      <div className="job-error">
                        <p>{job.error}</p>
                      </div>
                    )}

                    {job.status === 'completed' && job.result && (
                      <div className="job-result-analysis">
                        <AnalysisDisplay result={job.result} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {inputMode === 'text' && (
          <>
            {textStatus === 'idle' && (
              <>
                <textarea
                  className="text-input"
                  placeholder="Hujjat matnini bu yerga kiriting..."
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  rows={10}
                />
                {rawText.trim() && (
                  <button className="upload-btn" onClick={analyzeText}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="m5 12 7-7 7 7" />
                      <path d="M12 19V5" />
                    </svg>
                    Tahlil qilish
                  </button>
                )}
              </>
            )}

            {textStatus === 'processing' && (
              <div className="processing-state">
                <div className="spinner" />
                <p className="processing-text">Matn tahlil qilinmoqda...</p>
                <p className="processing-hint">Bu bir necha daqiqa davom etishi mumkin</p>
              </div>
            )}

            {textStatus === 'error' && (
              <div className="error-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                <p>{textError}</p>
                <button className="retry-btn" onClick={resetText}>Qayta urinish</button>
              </div>
            )}

            {textStatus === 'completed' && textResult && (
              <div className="result-container">
                <AnalysisDisplay result={textResult} />
                <button className="retry-btn" onClick={resetText}>Yangi tahlil</button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function AnalysisDisplay({ result }: { result: AnalysisResult }) {
  return (
    <>
      {result.summary && (
        <section className="card">
          <h3>Qisqacha mazmun</h3>
          <p className="summary-text">{result.summary}</p>
        </section>
      )}

      {result.author_info && (
        <section className="card">
          <h3>Murojaat qiluvchi</h3>
          <AuthorCard info={result.author_info} />
        </section>
      )}

      {result.department && result.department.full_name && (
        <section className="card">
          <h3>Mas'ul xodim</h3>
          <DepartmentCard dept={result.department} />
        </section>
      )}

      {result.issues && ((result.issues.issues?.length ?? 0) > 0 || (result.issues.keywords?.length ?? 0) > 0) && (
        <section className="card">
          <h3>Muammolar va kalit so'zlar</h3>
          {(result.issues.issues?.length ?? 0) > 0 && (
            <ul className="issues-list">
              {result.issues.issues!.map((issue, i) => <li key={i}>{issue}</li>)}
            </ul>
          )}
          {(result.issues.keywords?.length ?? 0) > 0 && (
            <div className="keywords">
              {result.issues.keywords!.map((kw, i) => (
                <span className="keyword-tag" key={i}>{kw}</span>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="meta-row">
        {result.entity?.entity_type && (
          <div className="meta-chip">
            {result.entity.entity_type === 'individual' ? 'Jismoniy shaxs' : 'Yuridik shaxs'}
          </div>
        )}
        {result.is_repeated && (
          <div className="meta-chip repeated">Takroriy murojaat</div>
        )}
      </div>
    </>
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

function AuthorCard({ info }: { info: AuthorInfo }) {
  const fullName = [info.last_name, info.first_name, info.middle_name].filter(Boolean).join(' ')
  const fields: [string, string | undefined][] = [
    ['Tug\'ilgan sana', info.date_of_birth],
    ['Jinsi', info.gender === 'male' ? 'Erkak' : info.gender === 'female' ? 'Ayol' : undefined],
    ['Telefon', info.phones?.join(', ')],
    ['Email', info.email],
    ['Viloyat', info.region],
    ['Tuman', info.district],
    ['Shahar', info.city],
    ['Manzil', info.address],
    ['Hujjat sanasi', info.date_when_document_was_written],
  ]

  return (
    <div className="author-card">
      {fullName && <p className="author-name">{fullName}</p>}
      <div className="author-fields">
        {fields.map(
          ([label, val]) =>
            val && (
              <div className="author-field" key={label}>
                <span className="field-label">{label}</span>
                <span className="field-value">{val}</span>
              </div>
            ),
        )}
      </div>
    </div>
  )
}

function DepartmentCard({ dept }: { dept: Department }) {
  return (
    <div className="dept-card">
      <p className="dept-name">{dept.full_name}</p>
      <p className="dept-position">{dept.position}</p>
      {dept.reasoning && <p className="dept-reasoning">{dept.reasoning}</p>}
      {(dept.responsibilities?.length ?? 0) > 0 && (
        <div className="keywords">
          {dept.responsibilities!.map((r, i) => (
            <span className="keyword-tag" key={i}>{r}</span>
          ))}
        </div>
      )}
    </div>
  )
}
