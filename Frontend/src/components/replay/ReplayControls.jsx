import { useEffect, useRef, useState } from 'react'

import usePipelineStore from '../../store/pipelineStore'


export default function ReplayControls() {
  const replayNodes = usePipelineStore((s) => s.replayNodes)
  const replayIndex = usePipelineStore((s) => s.replayIndex)
  const nodes = usePipelineStore((s) => s.nodes)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const nextReplayStep = usePipelineStore((s) => s.nextReplayStep)
  const prevReplayStep = usePipelineStore((s) => s.prevReplayStep)
  const stopReplay = usePipelineStore((s) => s.stopReplay)

  const [playing, setPlaying] = useState(false)
  const timeoutRef = useRef(null)

  const currentNodeId = replayNodes[replayIndex]
  const currentNode = nodes.find((n) => n.id === currentNodeId)
  const currentResult = nodeResults[currentNodeId]
  const atStart = replayIndex <= 0
  const atEnd = replayIndex >= replayNodes.length - 1


  useEffect(() => {
    if (!playing) return undefined
    if (atEnd) { setPlaying(false); return undefined }
    timeoutRef.current = setTimeout(() => nextReplayStep(), 1200)
    return () => clearTimeout(timeoutRef.current)
  }, [playing, replayIndex, atEnd, nextReplayStep])

  // Leaving replay mode (component unmount, e.g. canvas reset) shouldn't leave a dangling timer.
  useEffect(() => () => clearTimeout(timeoutRef.current), [])

  if (replayNodes.length === 0) return null

  const handleExit = () => {
    setPlaying(false)
    stopReplay()
  }

  return (
    <div className="absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] px-3 py-2 shadow-[var(--shadow-2)]">
      <span className="text-xs font-medium text-[var(--text-muted)] whitespace-nowrap">
        Step {replayIndex + 1} of {replayNodes.length}
      </span>

      <span className="text-sm font-medium text-[var(--text)] whitespace-nowrap">
        {currentNode?.data?.displayName || currentNodeId || '—'}
      </span>

      {currentResult?.success && currentResult.total_row_count != null && (
        <span className="rounded-full bg-[var(--accent-bg)] px-2 py-0.5 text-xs text-[var(--accent)] whitespace-nowrap">
          {currentResult.total_row_count.toLocaleString()} rows
        </span>
      )}
      {currentResult && !currentResult.success && (
        <span className="rounded-full bg-[var(--error)]/10 px-2 py-0.5 text-xs text-[var(--error)] whitespace-nowrap">
          failed
        </span>
      )}

      <span className="ui-divider" />

      <button
        type="button"
        onClick={prevReplayStep}
        disabled={atStart}
        className="ui-btn ui-btn-ghost"
      >
        ◀ Prev
      </button>
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        className="ui-btn ui-btn-ghost"
      >
        {playing ? '⏸ Pause' : '▶ Play'}
      </button>
      <button
        type="button"
        onClick={nextReplayStep}
        disabled={atEnd}
        className="ui-btn ui-btn-ghost"
      >
        Next ▶
      </button>

      <span className="ui-divider" />

      <button
        type="button"
        onClick={handleExit}
        className="ui-btn ui-btn-danger"
      >
        Exit Replay ✕
      </button>
    </div>
  )
}
