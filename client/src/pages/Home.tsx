import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import './Home.css'

const ROOM_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ'
const PRESET_NAMES = ['爸爸', '妈妈', '姐姐', '我']
const FAMILY_ROOM = '一家人'

function generateRoomCode(): string {
  let code = ''
  for (let i = 0; i < 6; i++) {
    code += ROOM_CHARS[Math.floor(Math.random() * ROOM_CHARS.length)]
  }
  return code
}

function Home() {
  const [searchParams] = useSearchParams()
  const [playerName, setPlayerName] = useState(searchParams.get('name') || '')
  const [roomId, setRoomId] = useState('')
  const navigate = useNavigate()

  const handleJoin = (room?: string, name?: string) => {
    const id = (room || roomId).trim()
    if (!id) return
    const n = (name || playerName).trim() || 'Player'
    navigate(`/room/${id}?name=${encodeURIComponent(n)}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleJoin()
  }

  const handleRandomCode = () => {
    setRoomId(generateRoomCode())
  }

  const handlePreset = (name: string) => {
    setPlayerName(name)
    // Auto-join family room if a preset name is selected
    if (!roomId) {
      setRoomId(FAMILY_ROOM)
      setTimeout(() => handleJoin(FAMILY_ROOM, name), 50)
    }
  }

  return (
    <div className="home-page">
      <h1 className="home-title">
        跑得快
      </h1>
      <p className="home-subtitle">
        经典卡牌游戏 · 2~4 人
      </p>

      {/* Preset name buttons */}
      <div className="home-section">
        <p className="home-section-label">
          选择角色
        </p>
        <div className="home-preset-grid">
          {PRESET_NAMES.map((name) => (
            <button
              key={name}
              onClick={() => handlePreset(name)}
              className={`home-preset-btn${playerName === name ? ' home-preset-btn--active' : ''}`}
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      {/* Custom nickname */}
      <input
        type="text"
        value={playerName}
        onChange={(e) => setPlayerName(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="或输入自定义昵称"
        className="home-input home-input--full"
      />

      {/* Room code + Join */}
      <div className="home-section home-section--narrow">
        <p className="home-room-label">
          输入房间号加入游戏
        </p>
        <div className="home-room-row">
          <input
            type="text"
            value={roomId}
            onChange={(e) => setRoomId(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="6位房间号"
            maxLength={6}
            className="home-input"
          />
        </div>
        <div className="home-room-actions">
          <button
            onClick={handleRandomCode}
            className="home-btn"
          >
            随机房间号
          </button>
          <button
            onClick={() => handleJoin()}
            disabled={!roomId.trim()}
            className="home-btn-join"
          >
            加入
          </button>
        </div>

        {/* Quick join family room */}
        <button
          onClick={() => {
            const name = playerName.trim() || 'Player'
            handleJoin(FAMILY_ROOM, name)
          }}
          disabled={!playerName.trim()}
          className="home-btn-family"
        >
          🏠 快速加入「一家人」房间
        </button>
      </div>

      <p className="home-footer">
        第一位输入房间号的玩家将自动创建房间。
        <br />
        2~4 人全部准备后自动开始游戏。
        <br />
        选择角色后自动加入「一家人」房间，历史得分自动保存。
      </p>
    </div>
  )
}

export default Home
