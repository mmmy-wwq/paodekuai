import { useRef, useCallback } from 'react'

/**
 * Hook providing simple Web Audio API sound effects for the card game.
 * Sounds are synthesized programmatically — no external audio files needed.
 */
export function useSoundEffects() {
  const ctxRef = useRef<AudioContext | null>(null)

  const getCtx = useCallback((): AudioContext => {
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext()
    }
    // Resume if suspended (browsers require user gesture)
    if (ctxRef.current.state === 'suspended') {
      ctxRef.current.resume()
    }
    return ctxRef.current
  }, [])

  /** Play card sound — short crisp "snap" like cards hitting a table. */
  const playCardSound = useCallback(() => {
    try {
      const ctx = getCtx()
      const now = ctx.currentTime

      // White noise burst → crisp snap
      const bufferSize = ctx.sampleRate * 0.08 // 80ms
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
      const data = buffer.getChannelData(0)
      for (let i = 0; i < bufferSize; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.015))
      }

      const noise = ctx.createBufferSource()
      noise.buffer = buffer

      const filter = ctx.createBiquadFilter()
      filter.type = 'highpass'
      filter.frequency.setValueAtTime(3000, now)
      filter.frequency.exponentialRampToValueAtTime(800, now + 0.06)

      const gain = ctx.createGain()
      gain.gain.setValueAtTime(0.25, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08)

      noise.connect(filter)
      filter.connect(gain)
      gain.connect(ctx.destination)
      noise.start(now)
      noise.stop(now + 0.08)
    } catch {
      // Audio not available — silently ignore
    }
  }, [getCtx])

  /** Play pass sound — short low "thud". */
  const playPassSound = useCallback(() => {
    try {
      const ctx = getCtx()
      const now = ctx.currentTime

      const osc = ctx.createOscillator()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(220, now)
      osc.frequency.exponentialRampToValueAtTime(110, now + 0.12)

      const gain = ctx.createGain()
      gain.gain.setValueAtTime(0.15, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12)

      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(now)
      osc.stop(now + 0.12)
    } catch {
      // Audio not available
    }
  }, [getCtx])

  return { playCardSound, playPassSound }
}
