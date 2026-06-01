import { useState, useCallback } from 'react'

interface AvatarProps {
  /** Player name — used to look up named avatar and for fallback initial */
  name: string
  /** Avatar size in pixels (default: 48) */
  size?: number
  /** Additional class name */
  className?: string
}

/**
 * Name-based color palette for avatar fallback backgrounds.
 */
const AVATAR_COLORS: Record<string, string> = {
  '爸爸': '#4A90D9',
  '妈妈': '#E8917A',
  '姐姐': '#E8A0C8',
  '弟弟': '#5DBE8A',
  '默认': '#C8962E',
}

function getColor(name: string): string {
  for (const [key, color] of Object.entries(AVATAR_COLORS)) {
    if (name.includes(key)) return color
  }
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 55%, 50%)`
}

function getInitial(name: string): string {
  return name.charAt(0)
}

/**
 * Stages:
 *   0 → try /头像/{name}.jpg
 *   1 → try /头像/默认头像.png (user's default)
 *   2 → CSS fallback (colored circle + initial)
 */
function Avatar({ name, size = 48, className = '' }: AvatarProps) {
  const [stage, setStage] = useState(0)

  const handleError = useCallback(() => {
    setStage((s) => s + 1)
  }, [])

  const imgProps = {
    width: size,
    height: size,
    onError: handleError,
    className: `player-avatar${className ? ' ' + className : ''}`,
    style: {
      width: size,
      height: size,
      borderRadius: '50%' as const,
      objectFit: 'cover' as const,
      flexShrink: 0,
    },
  }

  if (stage === 0) {
    return <img {...imgProps} src={`/头像/${encodeURIComponent(name)}.jpg`} alt={name} />
  }

  if (stage === 1) {
    return <img {...imgProps} src="/头像/默认头像.png" alt={name} />
  }

  // Stage 2: CSS fallback
  const bgColor = getColor(name)
  const initial = getInitial(name)
  const fontSize = Math.round(size * 0.42)

  return (
    <div
      className={`player-avatar player-avatar--fallback${className ? ' ' + className : ''}`}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: bgColor,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          fontSize,
          fontWeight: 700,
          color: '#ffffff',
          lineHeight: 1,
          textShadow: '0 1px 3px rgba(0,0,0,0.3)',
        }}
      >
        {initial}
      </span>
    </div>
  )
}

export default Avatar
