import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

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

  const btnBase: React.CSSProperties = {
    padding: '0.6rem 0.8rem',
    borderRadius: '8px',
    border: '2px solid var(--accent-gold)',
    background: 'rgba(255,255,255,0.08)',
    color: 'var(--text-secondary)',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    flex: 1,
    textAlign: 'center' as const,
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      padding: '2rem',
      gap: '1.2rem',
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

      {/* Preset name buttons */}
      <div style={{ maxWidth: '340px', width: '100%' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.4rem', textAlign: 'center' }}>
          选择角色
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          {PRESET_NAMES.map((name) => (
            <button
              key={name}
              onClick={() => handlePreset(name)}
              style={{
                ...btnBase,
                background: playerName === name
                  ? 'rgba(212, 160, 23, 0.25)'
                  : 'rgba(255,255,255,0.08)',
                borderColor: playerName === name ? 'var(--accent-gold)' : 'rgba(255,255,255,0.2)',
                color: playerName === name ? '#fff' : 'var(--text-secondary)',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.15)' }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = playerName === name
                  ? 'rgba(212, 160, 23, 0.25)'
                  : 'rgba(255,255,255,0.08)'
              }}
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
            onClick={() => handleJoin()}
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

        {/* Quick join family room */}
        <button
          onClick={() => {
            const name = playerName.trim() || 'Player'
            handleJoin(FAMILY_ROOM, name)
          }}
          disabled={!playerName.trim()}
          style={{
            width: '100%',
            marginTop: '0.6rem',
            padding: '0.75rem 1.5rem',
            borderRadius: '8px',
            border: '2px solid #43a047',
            background: playerName.trim() ? 'rgba(67, 160, 71, 0.15)' : 'rgba(255,255,255,0.03)',
            color: playerName.trim() ? '#43a047' : 'var(--text-secondary)',
            fontWeight: 'bold',
            fontSize: '1rem',
            cursor: playerName.trim() ? 'pointer' : 'not-allowed',
            opacity: playerName.trim() ? 1 : 0.4,
          }}
        >
          🏠 快速加入「一家人」房间
        </button>
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
        <br />
        选择角色后自动加入「一家人」房间，历史得分自动保存。
      </p>
    </div>
  )
}

export default Home
