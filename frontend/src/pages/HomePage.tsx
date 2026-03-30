import { Link } from 'react-router-dom'
import './HomePage.css'

const services = [
  {
    title: 'Rasmdan matn AI',
    description: "Hujjatlarni sun'iy intellekt yordamida qayta ishlash",
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
    title: "Murojaatlar",
    description: "Fuqarolarning murojaatlarini qabul qilish",
    path: '#',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    title: "Yangiliklar",
    description: "Tuman hokimligi yangiliklari va e'lonlari",
    path: '#',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" />
        <path d="M18 14h-8" />
        <path d="M15 18h-5" />
        <rect x="10" y="6" width="8" height="4" rx="1" />
      </svg>
    ),
  },
  {
    title: "Statistika",
    description: "Tuman bo'yicha statistik ma'lumotlar",
    path: '#',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 20V10" />
        <path d="M12 20V4" />
        <path d="M6 20v-6" />
      </svg>
    ),
  },
]

export default function HomePage() {
  return (
    <div className="home">
      <div className="home-pattern" />

      <header className="home-header">
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
