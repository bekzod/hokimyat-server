import { BrowserRouter, Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import OcrPage from './pages/OcrPage'
import LettersPage from './pages/LettersPage'
import MeetingPage from './pages/MeetingPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/ocr" element={<OcrPage />} />
        <Route path="/letters" element={<LettersPage />} />
        <Route path="/meeting" element={<MeetingPage />} />
      </Routes>
    </BrowserRouter>
  )
}
