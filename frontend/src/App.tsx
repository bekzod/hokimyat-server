import { BrowserRouter, Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import OcrPage from './pages/OcrPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/ocr" element={<OcrPage />} />
      </Routes>
    </BrowserRouter>
  )
}
