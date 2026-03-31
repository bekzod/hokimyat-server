import { useState, useCallback, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import './MeetingPage.css'

type InputMode = 'upload' | 'mic'
type TranscriptStatus = 'idle' | 'uploading' | 'recording' | 'saving' | 'completed' | 'error'

interface SavedAudio {
  key: string
  size: number
  filename?: string
  session_id?: string
}

export default function MeetingPage() {
  const [inputMode, setInputMode] = useState<InputMode>('upload')
  const [status, setStatus] = useState<TranscriptStatus>('idle')
  const [savedAudio, setSavedAudio] = useState<SavedAudio | null>(null)
  const [error, setError] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [fileName, setFileName] = useState('')
  const [recordingTime, setRecordingTime] = useState(0)
  const [audioLevel, setAudioLevel] = useState(0)
  const [streamBytes, setStreamBytes] = useState(0)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animFrameRef = useRef<number>(0)
  const audioCtxRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    return () => {
      cleanup()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const cleanup = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close()
      audioCtxRef.current = null
    }
    analyserRef.current = null
  }

  const reset = () => {
    cleanup()
    setStatus('idle')
    setSavedAudio(null)
    setError('')
    setUploadProgress(0)
    setFileName('')
    setRecordingTime(0)
    setAudioLevel(0)
    setStreamBytes(0)
  }

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    uploadAudio(file)
    // reset input so same file can be re-selected
    e.target.value = ''
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const file = e.dataTransfer.files[0]
    if (!file) return
    const audioTypes = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4', 'audio/webm', 'audio/flac', 'audio/x-m4a']
    if (!audioTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|ogg|m4a|flac|webm|mp4)$/i)) {
      setError('Faqat audio fayllar qabul qilinadi')
      setStatus('error')
      return
    }
    setFileName(file.name)
    uploadAudio(file)
  }, [])

  const uploadAudio = (file: File) => {
    setStatus('uploading')
    setUploadProgress(0)
    setError('')

    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        setUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          setSavedAudio({
            key: data.key,
            size: data.size,
            filename: data.filename,
          })
          setStatus('completed')
        } catch {
          setError('Server javobini o\'qib bo\'lmadi')
          setStatus('error')
        }
      } else {
        let msg = `Server xatosi: ${xhr.status}`
        try { msg = JSON.parse(xhr.responseText).detail || msg } catch { /* */ }
        setError(msg)
        setStatus('error')
      }
    })
    xhr.addEventListener('error', () => {
      setError('Tarmoq xatosi')
      setStatus('error')
    })
    xhr.open('POST', '/api/meeting/upload/')
    xhr.send(form)
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      // Audio level visualization
      const audioCtx = new AudioContext()
      audioCtxRef.current = audioCtx
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserRef.current = analyser

      const updateLevel = () => {
        if (!analyserRef.current) return
        const data = new Uint8Array(analyserRef.current.frequencyBinCount)
        analyserRef.current.getByteFrequencyData(data)
        const avg = data.reduce((a, b) => a + b, 0) / data.length
        setAudioLevel(avg / 255)
        animFrameRef.current = requestAnimationFrame(updateLevel)
      }
      updateLevel()

      // Connect WebSocket for real-time streaming
      const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${wsProto}//${window.location.host}/api/meeting/stream`)
      wsRef.current = ws

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data)
          if (msg.type === 'ack') {
            setStreamBytes(msg.received_bytes)
          } else if (msg.type === 'saved') {
            setSavedAudio({
              key: msg.key,
              size: msg.size,
              session_id: msg.session_id,
            })
            setStatus('completed')
          } else if (msg.type === 'error') {
            setError(msg.message || 'Server xatosi')
            setStatus('error')
          }
        } catch { /* ignore non-json */ }
      }

      ws.onerror = () => {
        setError("WebSocket ulanishida xatolik")
        setStatus('error')
        cleanup()
      }

      ws.onclose = () => {
        // if we're still recording, it means unexpected disconnect
        if (status === 'recording') {
          // state might have already transitioned
        }
      }

      // Wait for WebSocket to be ready before starting MediaRecorder
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve()
        ws.onerror = () => reject(new Error('WebSocket failed'))
      })

      // Start MediaRecorder and stream chunks via WebSocket
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recorder.ondataavailable = async (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          const buffer = await e.data.arrayBuffer()
          wsRef.current.send(buffer)
        }
      }
      // Send chunks every 250ms for near-real-time streaming
      recorder.start(250)
      mediaRecorderRef.current = recorder

      setStatus('recording')
      setRecordingTime(0)
      setStreamBytes(0)

      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1)
      }, 1000)
    } catch {
      setError("Mikrofonga ruxsat berilmadi")
      setStatus('error')
      cleanup()
    }
  }

  const stopRecording = () => {
    // Stop the MediaRecorder first — this flushes remaining data
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }

    // Stop mic stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }

    // Stop timer & visualizer
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close()
      audioCtxRef.current = null
    }
    analyserRef.current = null

    // Tell server to finalize — small delay so last chunks arrive
    setStatus('saving')
    setTimeout(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'stop' }))
      }
    }, 500)
  }

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = (secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="meeting">
      <nav className="ocr-nav">
        <Link to="/" className="back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
          Bosh sahifa
        </Link>
        <h1 className="ocr-nav-title">Majlis stenografiyasi</h1>
        <div className="nav-links">
          <Link to="/ocr" className="nav-link">OCR</Link>
          <Link to="/letters" className="nav-link">Hatlar</Link>
        </div>
      </nav>

      <main className="meeting-main">
        {(status === 'idle' || status === 'recording') && (
          <div className="mode-toggle">
            <button
              className={`mode-btn ${inputMode === 'upload' ? 'active' : ''}`}
              onClick={() => { if (status !== 'recording') setInputMode('upload') }}
              disabled={status === 'recording'}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mode-icon">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              Audio yuklash
            </button>
            <button
              className={`mode-btn ${inputMode === 'mic' ? 'active' : ''}`}
              onClick={() => { if (status !== 'recording') setInputMode('mic') }}
              disabled={status === 'recording'}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mode-icon">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
              Jonli yozish
            </button>
          </div>
        )}

        {inputMode === 'upload' && status === 'idle' && (
          <div
            className="audio-drop-zone"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }}
            onDragLeave={(e) => e.currentTarget.classList.remove('drag-over')}
            onDrop={(e) => { e.currentTarget.classList.remove('drag-over'); handleDrop(e) }}
          >
            <div className="audio-drop-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18V5l12-2v13" />
                <circle cx="6" cy="18" r="3" />
                <circle cx="18" cy="16" r="3" />
              </svg>
            </div>
            <p className="drop-text">Audio faylni bu yerga tashlang</p>
            <p className="drop-hint">yoki tanlash uchun bosing</p>
            <p className="drop-formats">MP3, WAV, OGG, M4A, FLAC, WebM</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.mp3,.wav,.ogg,.m4a,.flac,.webm"
              onChange={handleFileSelect}
              hidden
            />
          </div>
        )}

        {inputMode === 'mic' && status === 'idle' && (
          <div className="mic-section">
            <button className="mic-start-btn" onClick={startRecording}>
              <div className="mic-btn-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="22" />
                </svg>
              </div>
              Yozishni boshlash
            </button>
            <p className="mic-hint">Mikrofon orqali majlis yozib olinadi — audio real vaqtda serverga uzatiladi</p>
          </div>
        )}

        {status === 'recording' && (
          <div className="recording-section">
            <div className="recording-visualizer">
              <div className="recording-pulse" style={{ transform: `scale(${1 + audioLevel * 0.5})` }} />
              <div className="recording-dot" />
            </div>
            <p className="recording-time">{formatTime(recordingTime)}</p>
            <p className="recording-label">Yozilmoqda...</p>
            <div className="level-bar-container">
              <div className="level-bar" style={{ width: `${audioLevel * 100}%` }} />
            </div>
            {streamBytes > 0 && (
              <p className="stream-info">Uzatildi: {formatSize(streamBytes)}</p>
            )}
            <button className="stop-btn" onClick={stopRecording}>
              <svg viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
              To'xtatish
            </button>
          </div>
        )}

        {status === 'uploading' && (
          <div className="upload-state">
            <div className="upload-file-info">
              <svg className="upload-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M9 18V5l12-2v13" />
                <circle cx="6" cy="18" r="3" />
                <circle cx="18" cy="16" r="3" />
              </svg>
              <span>{fileName}</span>
            </div>
            <div className="job-progress">
              <div className="progress-bar-container">
                <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
              </div>
              <span className="progress-label">{uploadProgress}%</span>
            </div>
            <p className="upload-hint">Yuklanmoqda...</p>
          </div>
        )}

        {status === 'saving' && (
          <div className="processing-state">
            <div className="spinner" />
            <p className="processing-text">Audio saqlanmoqda...</p>
            <p className="processing-hint">Yozuv serverga saqlanmoqda</p>
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

        {status === 'completed' && savedAudio && (
          <div className="transcript-result">
            <div className="transcript-header">
              <h2>Audio saqlandi</h2>
            </div>
            <div className="saved-audio-card">
              <div className="saved-audio-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 18V5l12-2v13" />
                  <circle cx="6" cy="18" r="3" />
                  <circle cx="18" cy="16" r="3" />
                </svg>
              </div>
              <div className="saved-audio-details">
                {savedAudio.filename && <p className="saved-filename">{savedAudio.filename}</p>}
                {savedAudio.session_id && <p className="saved-filename">Jonli yozuv</p>}
                <p className="saved-meta">
                  {formatSize(savedAudio.size)}
                  <span className="saved-key">{savedAudio.key}</span>
                </p>
              </div>
              <div className="saved-check">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
            </div>
            <button className="retry-btn" onClick={reset}>Yangi audio</button>
          </div>
        )}
      </main>
    </div>
  )
}
