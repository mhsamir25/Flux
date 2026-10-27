import usePipelineStore from '../../store/pipelineStore'

export default function CanvasToolbar() {
  const mouseMode = usePipelineStore((s) => s.mouseMode)
  const setMouseMode = usePipelineStore((s) => s.setMouseMode)
  const nodes = usePipelineStore((s) => s.nodes)
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const selectedNodeIds = usePipelineStore((s) => s.selectedNodeIds)
  const deleteSelectedNodes = usePipelineStore((s) => s.deleteSelectedNodes)
  const clearSelection = usePipelineStore((s) => s.clearSelection)

  // Identify all selected nodes
  const selectedCount = Math.max(
    (selectedNodeIds || []).length,
    nodes.filter((n) => n.selected).length,
    selectedNodeId ? 1 : 0
  )

  return (
    <div className="absolute top-3 left-3 z-20 flex items-center gap-1.5 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] p-1 shadow-[var(--shadow-2)]">
      {/* Mode toggle button group */}
      <div className="flex items-center rounded border border-[var(--border-light)] bg-[var(--panel-alt)] p-0.5">
        <button
          type="button"
          onClick={() => setMouseMode('select')}
          className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors ${
            mouseMode === 'select'
              ? 'border border-[var(--border-light)] bg-[var(--panel)] font-semibold text-[var(--accent)] shadow-xs'
              : 'text-[var(--text-muted)] hover:text-[var(--text)]'
          }`}
          title="Select Mode (V) — Drag across canvas to box-select multiple nodes"
          aria-label="Select mode"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3l7 18 3-7 7-3L3 3z" />
          </svg>
          <span>Select</span>
          <kbd className="ml-0.5 text-[10px] opacity-60">V</kbd>
        </button>

        <button
          type="button"
          onClick={() => setMouseMode('pan')}
          className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors ${
            mouseMode === 'pan'
              ? 'border border-[var(--border-light)] bg-[var(--panel)] font-semibold text-[var(--accent)] shadow-xs'
              : 'text-[var(--text-muted)] hover:text-[var(--text)]'
          }`}
          title="Pan Mode (H) — Drag to pan canvas (or hold Space while in Select mode)"
          aria-label="Pan mode"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0" />
            <path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2" />
            <path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8" />
            <path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15" />
          </svg>
          <span>Pan</span>
          <kbd className="ml-0.5 text-[10px] opacity-60">H</kbd>
        </button>

        <button
          type="button"
          onClick={() => setMouseMode('deleteEdge')}
          className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors ${
            mouseMode === 'deleteEdge'
              ? 'border border-[var(--error)]/30 bg-[var(--panel)] font-semibold text-[var(--error)] shadow-xs'
              : 'text-[var(--text-muted)] hover:text-[var(--error)]'
          }`}
          title="Delete Edge Mode (D) — Click any edge to disconnect/delete it"
          aria-label="Delete edge mode"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="6" cy="6" r="3" />
            <circle cx="6" cy="18" r="3" />
            <line x1="20" y1="4" x2="8.12" y2="15.88" />
            <line x1="14.47" y1="14.48" x2="20" y2="20" />
            <line x1="8.12" y1="8.12" x2="12" y2="12" />
          </svg>
          <span>Delete Edge</span>
          <kbd className="ml-0.5 text-[10px] opacity-60">D</kbd>
        </button>
      </div>

      {/* When nodes are selected, show selection badge and delete button */}
      {selectedCount > 0 && (
        <>
          <span className="h-4 w-px bg-[var(--border)]" />

          <span className="rounded-[var(--radius)] bg-[var(--accent-bg)] px-2 py-0.5 text-xs font-medium text-[var(--accent)]">
            {selectedCount} selected
          </span>

          <button
            type="button"
            onClick={deleteSelectedNodes}
            className="flex items-center gap-1 rounded border border-[var(--border-light)] px-2 py-1 text-xs font-medium text-[var(--error)] transition-colors hover:border-[var(--error)]/30 hover:bg-[var(--error)]/10"
            title={`Delete ${selectedCount} selected ${selectedCount === 1 ? 'node' : 'nodes'} (Backspace or Delete)`}
            aria-label="Delete selected nodes"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
            <span>Delete {selectedCount > 1 ? `(${selectedCount})` : ''}</span>
            <kbd className="ml-0.5 text-[10px] opacity-70">Del</kbd>
          </button>

          <button
            type="button"
            onClick={clearSelection}
            className="rounded p-1 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--panel-hover)] hover:text-[var(--text)]"
            title="Deselect all (Esc)"
            aria-label="Deselect all"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </>
      )}
    </div>
  )
}
