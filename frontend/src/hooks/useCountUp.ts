import { useEffect, useRef, useState } from 'react'

/** Fast at first, settling at the end - a value arriving, not a slot machine. */
function easeOut(t: number) {
  return 1 - (1 - t) ** 3
}

/**
 * Run a figure up to its new value instead of swapping it.
 *
 * On a screen that refreshes on a timer, a number that changes silently is a
 * number nobody notices. Counting to it says "this moved" without a banner, a
 * highlight, or anything the operator has to dismiss.
 *
 * It counts from the *previous* value, not from zero, so a refresh that nudges
 * 207 to 209 is a small movement and not a full re-roll. Reduced motion gets
 * the value directly.
 */
export function useCountUp(value: number, durationMs = 900): number {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  const frame = useRef(0)

  useEffect(() => {
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    if (reduced || from.current === value) {
      from.current = value
      setShown(value)
      return
    }

    const start = performance.now()
    const origin = from.current
    const distance = value - origin

    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs)
      setShown(origin + distance * easeOut(progress))
      if (progress < 1) {
        frame.current = requestAnimationFrame(step)
      } else {
        from.current = value
      }
    }

    frame.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame.current)
  }, [value, durationMs])

  return shown
}
