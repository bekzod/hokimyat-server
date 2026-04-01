import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import './OfficialsPage.css'

interface Official {
  order: number
  position: string
  appointment_date: string | null
  full_name: string
  responsibilities: string[]
}

export default function OfficialsPage() {
  const [officials, setOfficials] = useState<Official[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/officials/')
      .then(res => {
        if (!res.ok) throw new Error('Ma\'lumotlarni yuklashda xatolik')
        return res.json()
      })
      .then(data => {
        setOfficials(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const formatDate = (date: string | null) => {
    if (!date) return 'Belgilanmagan'
    const d = new Date(date)
    return d.toLocaleDateString('uz-UZ', { year: 'numeric', month: 'long', day: 'numeric' })
  }

  return (
    <div className="officials">
      <nav className="officials-nav">
        <Link to="/" className="back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
          Bosh sahifa
        </Link>
        <span className="nav-title">Rahbariyat</span>
        <span />
      </nav>

      <header className="officials-header">
        <h1>Toshkent tumani hokimligi rahbariyati</h1>
        <p>Mansabdor shaxslar ro'yxati</p>
      </header>

      <main className="officials-main">
        {loading && (
          <div className="officials-loading">
            <div className="spinner" />
            <p>Yuklanmoqda...</p>
          </div>
        )}

        {error && (
          <div className="officials-error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && (
          <div className="officials-list">
            {officials.map(official => (
              <div key={official.order} className="official-card">
                <div className="official-order">{official.order}</div>
                <div className="official-info">
                  <h3 className="official-name">{official.full_name}</h3>
                  <p className="official-position">{official.position}</p>
                  <div className="official-meta">
                    <span className="official-date">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                        <line x1="16" y1="2" x2="16" y2="6" />
                        <line x1="8" y1="2" x2="8" y2="6" />
                        <line x1="3" y1="10" x2="21" y2="10" />
                      </svg>
                      {formatDate(official.appointment_date)}
                    </span>
                  </div>
                  <div className="official-tags">
                    {official.responsibilities.map(r => (
                      <span key={r} className="tag">{r}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
