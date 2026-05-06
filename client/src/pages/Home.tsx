import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const ROOM_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ'

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

  const handleJoin = () => {
    const id = roomId.trim()
    if (!id) return
    const name = playerName.trim() || 'Player'
    navigate(`/room/${id}?name=${encodeURIComponent(name)}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleJoin()
  }

  const handleRandomCode = () => {
    setRoomId(generateRoomCode())
  }

  const inputStyle: React.CSSProperties = {
    flex: 1,
    padding: '0.75rem 1rem',
    borderRadius: '8px',
    border: '2px solid var(--accent-gold)',
    background: 'rgba(255,255,255,0.1)',
    color: 'var(--text-primary)',
    fontSize: '1rem',
    outline: 'none',
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      padding: '2rem',
      gap: '1.5rem',
    }}>
      <h1 style={{
        fontSize: '2.5rem',
        fontWeight: 'bold',
        textShadow: '2px 2px 4px rgba(0,0,0,0.5)',
      }}>
        跑得快
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
        经典卡牌游戏 · 2~4 人
      </p>

      {/* Nickname */}
      <input
        type="text"
        value={playerName}
        onChange={(e) => setPlayerName(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="你的昵称"
        style={{ ...inputStyle, maxWidth: '320px', width: '100%' }}
      />

      {/* Room code + Join */}
      <div style={{ maxWidth: '320px', width: '100%' }}>
        <p style={{
          color: 'var(--text-secondary)',
          fontSize: '0.9rem',
          fontWeight: 600,
          marginBottom: '0.5rem',
          textAlign: 'center',
        }}>
          输入房间号加入游戏
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', width: '100%' }}>
          <input
            type="text"
            value={roomId}
            onChange={(e) => setRoomId(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="6位房间号"
            maxLength={6}
            style={inputStyle}
          />
        </div>
        <div style={{
          display: 'flex',
          gap: '0.5rem',
          width: '100%',
          marginTop: '0.5rem',
        }}>
          <button
            onClick={handleRandomCode}
            style={{
              flex: 1,
              padding: '0.6rem 1rem',
              borderRadius: '8px',
              border: '2px solid var(--accent-gold)',
              background: 'rgba(255,255,255,0.08)',
              color: 'var(--text-secondary)',
              fontSize: '0.85rem',
            }}
          >
            随机房间号
          </button>
          <button
            onClick={handleJoin}
            disabled={!roomId.trim()}
            style={{
              flex: 1,
              padding: '0.75rem 1.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'var(--accent-gold)',
              color: '#fff',
              fontWeight: 'bold',
              fontSize: '1rem',
              cursor: roomId.trim() ? 'pointer' : 'not-allowed',
              opacity: roomId.trim() ? 1 : 0.5,
            }}
          >
            加入
          </button>
        </div>
      </div>

      <p style={{
        color: 'var(--text-secondary)',
        fontSize: '0.8rem',
        maxWidth: '320px',
        textAlign: 'center',
        lineHeight: 1.5,
      }}>
        第一位输入房间号的玩家将自动创建房间。
        <br />
        2~4 人全部准备后自动开始游戏。
      </p>
    </div>
  )
}

export default Home
