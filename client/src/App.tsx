import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import GameRoom from './pages/GameRoom'
import { useMobileLandscape } from './hooks/useMobileLandscape'

function App() {
  useMobileLandscape()

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/room/:id" element={<GameRoom />} />
    </Routes>
  )
}

export default App
