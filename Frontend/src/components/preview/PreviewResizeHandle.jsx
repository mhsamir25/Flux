import { useCallback, useEffect, useRef, useState } from 'react'

import usePipelineStore from '../../store/pipelineStore'

// The preview panel is the second-biggest thing on screen after the canvas, and how much of
// it you want depends entirely on what you're doing: a sliver while you rearrange the
// graph, most of the window while you're reading a result table or looking at a chart. So its
// height is dragged rather than fixed.
//
// This handle lives between the canvas and the panel and is the only thing that writes
// previewHeight. Two snap points at the ends of the travel:
//   - dragged to the top    -> the panel takes the whole column ("whole page"), the canvas
//     shrinks to a sliver. A sliver, not zero: the handle has to stay reachable to drag back.
//   - dragged to the bottom -> the panel collapses to its header strip, giving the canvas
//     everything back.
// Anything in between is free, which is the point.

const MIN_HEIGHT = 44        // just the "Preview / N rows / Export" header
const SNAP = 16              // how close to an end counts as "snapped" to it
const MIN_CANVAS = 48        // canvas never fully vanishes, so this handle stays grabbable
const KEYBOARD_STEP = 24
const STORAGE_KEY = 'flux_preview_height'

function readStoredHeight() {
  try {
    const stored = Number(localStorage.getItem(STORAGE_KEY))
    // Guard against a corrupt/hand-edited value: a NaN height would collapse the panel.
    return Number.isFinite(stored) && stored > 0 ? stored : null
  } catch {
    return null
  }
}

export default function PreviewResizeHandle({ containerRef }) {
  const previewHeight = usePipelineStore((s) => s.previewHeight)
  const setPreviewHeight = usePipelineStore((s) => s.setPreviewHeight)

  // The column's own height is the ceiling — the panel can't grow past the space the canvas
  // and the upload zone leave it. It's tracked two ways on purpose:
  //   - maxHeightRef, read only inside event handlers, so a window resize *during* a drag is
  //     picked up immediately and the panel can't be dragged past the bottom of the screen;
  //   - maxHeightForAria, state, purely so aria-valuemax is accurate. Reading a ref during
  //     render is not allowed (and the React Compiler lint rule rightly rejects it).
  const maxHeightRef = useRef(0)
  const [maxHeightForAria, setMaxHeightForAria] = useState(0)

  const measure = useCallback(() => {
    const available = containerRef.current?.clientHeight ?? window.innerHeight
    const next = Math.max(MIN_HEIGHT, available - MIN_CANVAS)
    maxHeightRef.current = next
    setMaxHeightForAria(next)
  }, [containerRef])

  useEffect(() => {
    measure()
    const element = containerRef.current
    if (!element || typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure)
      return () => window.removeEventListener('resize', measure)
    }
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [containerRef, measure])

  const clamp = (value) => {
    const max = maxHeightRef.current || measure()
    if (value >= max - SNAP) return max
    if (value <= MIN_HEIGHT + SNAP) return MIN_HEIGHT
    return Math.min(max, Math.max(MIN_HEIGHT, value))
  }

  const apply = (value) => {
    const next = clamp(value)
    setPreviewHeight(next)
    try {
      localStorage.setItem(STORAGE_KEY, String(next))
    } catch {
      // Non-critical: the size just won't be remembered next session.
    }
  }

  // Restore a remembered size once on mount, and only if it still fits — a height saved on a
  // tall screen would otherwise open as an over-tall panel on a short one. In an effect, not
  // during render: writing to the store while rendering is how you get an update loop.
  useEffect(() => {
    const restored = readStoredHeight()
    if (restored === null) return
    measure()
    const max = maxHeightRef.current
    if (restored <= max) setPreviewHeight(restored)
    // Mount-only by design: the stored value is a starting point, not something that should
    // fight the user after they've dragged.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startDrag = (event) => {
    event.preventDefault()
    const startY = event.clientY
    const startHeight = previewHeight

    const onMove = (e) => apply(startHeight - (e.clientY - startY))
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      // Restore the cursor and text selection — without this the whole UI stays in
      // row-resize/unselectable after a drag that ends outside the handle.
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'row-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  // Keyboard-operable so the panel isn't mouse-only. Home/End jump to the two snap points.
  const onKeyDown = (event) => {
    const steps = {
      ArrowUp: KEYBOARD_STEP,
      ArrowDown: -KEYBOARD_STEP,
      PageUp: KEYBOARD_STEP * 2,
      PageDown: -KEYBOARD_STEP * 2,
    }
    if (event.key in steps) {
      event.preventDefault()
      apply(previewHeight + steps[event.key])
    } else if (event.key === 'Home') {
      event.preventDefault()
      apply(MIN_HEIGHT)
    } else if (event.key === 'End') {
      event.preventDefault()
      apply(maxHeightRef.current)
    }
  }

  return (
    <div
      role="separator"
      aria-orientation="horizontal"
      aria-label="Resize preview panel"
      aria-valuenow={Math.round(previewHeight)}
      aria-valuemin={MIN_HEIGHT}
      aria-valuemax={Math.round(maxHeightForAria)}
      tabIndex={0}
      onPointerDown={startDrag}
      onKeyDown={onKeyDown}
      title="Drag to resize the preview — up for the whole page, down to collapse"
      className="group relative h-2 shrink-0 cursor-row-resize touch-none bg-[var(--border)] outline-none transition-colors hover:bg-[var(--accent)] focus-visible:bg-[var(--accent)]"
    >
      {/* The grabber pill only appears on hover/focus, so it doesn't add permanent visual
          noise to the canvas edge but is still discoverable. */}
      <span className="pointer-events-none absolute left-1/2 top-1/2 h-1 w-10 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-70 group-focus-visible:opacity-70" />
    </div>
  )
}
