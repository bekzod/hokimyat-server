import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import './HomePage.css'

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'light' || saved === 'dark') return saved
    return 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggle = () => setTheme(t => t === 'light' ? 'dark' : 'light')
  return { theme, toggle }
}

const services = [
  {
    title: 'Rasmdan matn AI',
    description: "Rasmli hujjatlardan matn ajratib olish",
    path: '/ocr',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
        <path d="M14 2v6h6" />
        <path d="M9 15h6" />
        <path d="M9 11h6" />
      </svg>
    ),
  },
  {
    title: 'Hatlar AI',
    description: "Hatlarni sun'iy intellekt yordamida tahlil qilish",
    path: '/letters',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2Z" />
        <polyline points="22,6 12,13 2,6" />
      </svg>
    ),
  },
  {
    title: 'Majlis stenografiyasi',
    description: "Audio yozuvlarni matnga aylantirish",
    path: '/meeting',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="22" />
      </svg>
    ),
  },
]

export default function HomePage() {
  const { theme, toggle } = useTheme()

  return (
    <div className="home">
      <div className="home-pattern" />

      <header className="home-header">
        <button className="theme-toggle" onClick={toggle} aria-label="Rejimni almashtirish">
          {theme === 'light' ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          )}
        </button>
        <div className="gerb-container">
          <img src="/gerb.png" alt="O'zbekiston Respublikasi gerbi" className="gerb" />
        </div>

        <div className="header-text">
          <h1>Toshkent tuman hokimiyati</h1>
          <p className="subtitle">O'zbekiston Respublikasi</p>
        </div>

        <div className="header-rule">
          <span className="rule-ornament" />
          <span className="rule-diamond" />
          <span className="rule-ornament" />
        </div>
      </header>

      <main className="home-services">
        <h2 className="services-heading">Xizmatlar</h2>
        <div className="services-grid">
          {services.map((s) => (
            <Link to={s.path} key={s.title} className="service-card">
              <div className="service-icon">{s.icon}</div>
              <div className="service-body">
                <h3>{s.title}</h3>
                <p>{s.description}</p>
              </div>
              <svg className="service-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </Link>
          ))}
        </div>
      </main>

      <footer className="home-footer">
        <p>&copy; 2026 Toshkent tuman hokimiyati. Barcha huquqlar himoyalangan.</p>
      </footer>
    </div>
  )
}
