/**
 * Hook: Force landscape orientation on mobile via CSS transform.
 *
 * When the user holds the phone in portrait orientation on a touch device,
 * the entire app is rotated 90 degrees so the game appears in landscape
 * without requiring the user to physically rotate their phone.
 *
 * Uses CSS `transform: rotate(90deg)` (方案 A) because:
 * - `screen.orientation.lock('landscape')` is not supported on iOS Safari
 * - A "please rotate" overlay (方案 C) is unreliable — the user reported
 *   that rotating the phone did not dismiss it in a previous version
 *
 * Additionally tries `screen.orientation.lock()` on first user tap,
 * which gives a native landscape experience on Android Chrome.
 */

import { useEffect, useRef } from 'react'

/** Attempt to lock screen orientation (Android Chrome). */
async function tryLockOrientation(): Promise<void> {
  try {
    const orient = (screen as any).orientation
    if (orient && typeof orient.lock === 'function') {
      await orient.lock('landscape-primary')
    }
  } catch {
    // Not supported (iOS) — CSS rotation handles it
  }
}

/**
 * Apply CSS custom properties for the dynamic viewport height/width,
 * which accounts for the address bar on iOS Safari 15.4+.
 */
function setViewportUnits(): void {
  const root = document.documentElement
  root.style.setProperty('--dvh', `${window.innerHeight * 0.01}px`)
  root.style.setProperty('--dvw', `${window.innerWidth * 0.01}px`)
}

/**
 * Installs the force-landscape behaviour. Call once from the app root.
 *
 * - Adds/removes `.force-landscape` class on `<html>` based on
 *   `(pointer: coarse) && (orientation: portrait)`
 * - Re-checks on orientation change and window resize
 * - Tries native orientation lock on first user tap
 * - Updates dynamic viewport units on resize
 */
export function useMobileLandscape(): void {
  const appliedRef = useRef(false)

  useEffect(() => {
    const html = document.documentElement
    const root = document.getElementById('root')
    if (!root) return

    const apply = () => {
      const isMobile = window.matchMedia('(pointer: coarse)').matches
      const isPortrait = window.matchMedia('(orientation: portrait)').matches
      setViewportUnits()

      if (isMobile && isPortrait) {
        html.classList.add('force-landscape')
        appliedRef.current = true
      } else {
        html.classList.remove('force-landscape')
        appliedRef.current = false
      }
    }

    apply()

    // Try native orientation lock on first user tap (Android only)
    const onFirstTap = () => {
      tryLockOrientation()
      document.removeEventListener('pointerdown', onFirstTap)
    }
    document.addEventListener('pointerdown', onFirstTap, { once: true })

    // Listen for orientation / resize changes
    const portraitMql = window.matchMedia('(orientation: portrait)')
    portraitMql.addEventListener('change', apply)
    window.addEventListener('resize', apply)

    return () => {
      portraitMql.removeEventListener('change', apply)
      window.removeEventListener('resize', apply)
      document.removeEventListener('pointerdown', onFirstTap)
      html.classList.remove('force-landscape')
    }
  }, [])
}
