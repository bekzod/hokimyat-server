import { useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import './OcrPage.css'

type Status = 'idle' | 'uploading' | 'processing' | 'completed' | 'error'

interface OcrResult {
  content: string
  meta: Record<string, unknown>
  total_page_count: number
}

export default function OcrPage() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<OcrResult | null>(null)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval>>(undefined)

  const reset = () => {
    setFile(null)
    setStatus('idle')
    setResult(null)
    setError('')
    if (pollingRef.current) clearInterval(pollingRef.current)
  }

  const pollStatus = useCallback((fileId: string) => {
    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${fileId}`)
        if (!res.ok) throw new Error('Status check failed')
        const data = await res.json()

        if (data.status === 'completed') {
          clearInterval(pollingRef.current)
          setResult({
            content: data.content || '',
            meta: data.meta || {},
            total_page_count: data.total_page_count || 0,
          })
          setStatus('completed')
        } else if (data.status === 'error') {
          clearInterval(pollingRef.current)
          setError(data.error_message || 'Xatolik yuz berdi')
          setStatus('error')
        }
      } catch {
        clearInterval(pollingRef.current)
        setError("Serverga ulanib bo'lmadi")
        setStatus('error')
      }
    }, 2000)
  }, [])

  const upload = async () => {
    if (!file) return
    setStatus('uploading')
    setError('')
    setResult(null)

    try {
      const form = new FormData()
      form.append('file', file)

      const res = await fetch('/api/upload-document/', { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail || `Server xatosi: ${res.status}`)
      }

      const data = await res.json()
      setStatus('processing')
      pollStatus(data.file_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Xatolik yuz berdi')
      setStatus('error')
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

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

      <main className="ocr-main">
        {status === 'idle' && (
          <div
            className={`drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) setFile(f)
              }}
            />
            {file ? (
              <div className="file-preview">
                <svg className="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                  <path d="M14 2v6h6" />
                </svg>
                <span className="file-name">{file.name}</span>
                <span className="file-size">{(file.size / 1024).toFixed(0)} KB</span>
              </div>
            ) : (
              <>
                <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <p className="drop-text">Faylni bu yerga tashlang yoki bosing</p>
                <p className="drop-hint">PDF, PNG, JPG, TIFF</p>
              </>
            )}
          </div>
        )}

        {status === 'idle' && file && (
          <button className="upload-btn" onClick={upload}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m5 12 7-7 7 7" />
              <path d="M12 19V5" />
            </svg>
            Yuklash va tahlil qilish
          </button>
        )}

        {(status === 'uploading' || status === 'processing') && (
          <div className="processing-state">
            <div className="spinner" />
            <p className="processing-text">
              {status === 'uploading' ? 'Fayl yuklanmoqda...' : "Hujjat tahlil qilinmoqda..."}
            </p>
            <p className="processing-hint">Bu bir necha daqiqa davom etishi mumkin</p>
          </div>
        )}

        {status === 'error' && (
          <div className="error-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            <p>{error}</p>
            <button className="retry-btn" onClick={reset}>Qayta urinish</button>
          </div>
        )}

        {status === 'completed' && result && (
          <div className="result-container">
            <div className="result-header">
              <h2>Natija</h2>
              {result.total_page_count > 0 && (
                <span className="page-badge">{result.total_page_count} sahifa</span>
              )}
            </div>

            {result.content && (
              <div className="result-section">
                <h3>Matn</h3>
                <pre className="result-content">{result.content}</pre>
              </div>
            )}

            {Object.keys(result.meta).length > 0 && (
              <div className="result-section">
                <h3>Metadata</h3>
                <div className="meta-grid">
                  {Object.entries(result.meta).map(([key, val]) => (
                    <div className="meta-item" key={key}>
                      <span className="meta-key">{key}</span>
                      <span className="meta-val">{typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button className="retry-btn" onClick={reset}>Yangi hujjat yuklash</button>
          </div>
        )}
      </main>
    </div>
  )
}
