import { useRef } from 'react'

import usePipelineStore from '../../store/pipelineStore'

// Save is visible always, guest or not (PLAN.md §12) — App.jsx's onSave prop decides whether
// clicking it saves immediately or opens the auth modal first. Pipeline JSON export/import is
// pure client-side file I/O (§14) — works identically for guests, no backend call at all.
export default function TopBar({ onShowTemplates, onShowAuth, onSave }) {
  const username = usePipelineStore((s) => s.username)
  const clearAuth = usePipelineStore((s) => s.clearAuth)
  const resetCanvas = usePipelineStore((s) => s.resetCanvas)
  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const csvData = usePipelineStore((s) => s.csvData)
  const loadPipeline = usePipelineStore((s) => s.loadPipeline)
  const setCsvData = usePipelineStore((s) => s.setCsvData)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const replayNodes = usePipelineStore((s) => s.replayNodes)
  const startReplay = usePipelineStore((s) => s.startReplay)
  const currentTemplateName = usePipelineStore((s) => s.currentTemplateName)
  const setCurrentTemplate = usePipelineStore((s) => s.setCurrentTemplate)
  const importInputRef = useRef(null)

  const hasResults = Object.keys(nodeResults).length > 0
  const isReplaying = replayNodes.length > 0

  const handleNew = () => {
    if (nodes.length > 0 && !window.confirm('Clear the canvas and start a new pipeline?')) return
    resetCanvas()
  }

  const handleExportJson = () => {
    const payload = JSON.stringify({ version: '1.0', nodes, edges, csvData }, null, 2)
    const blob = new Blob([payload], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'flux-pipeline.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImportJson = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        throw new Error('File is missing nodes/edges arrays.')
      }
      loadPipeline(parsed.nodes, parsed.edges)
      if (parsed.csvData) setCsvData(parsed.csvData, file.name)
    } catch (err) {
      window.alert(`Could not import pipeline: ${err.message}`)
    }
  }

  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--panel)] px-3">
      <div className="flex items-center gap-2">
        <span className="rounded-[var(--radius)] bg-[var(--accent)] px-1.5 py-0.5 text-xs font-semibold text-[var(--accent-text)]">
          Flux
        </span>
        <span className="text-xs text-[var(--text-muted)]">no-code pipeline builder</span>
        {currentTemplateName && (
          <div className="flex items-center gap-1 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel-alt)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
            <span>Template:</span>
            <span className="font-medium text-[var(--text)]">{currentTemplateName}</span>
            <button
              type="button"
              onClick={() => setCurrentTemplate(null, null)}
              title="Detach template (save as new pipeline)"
              className="ml-1 text-[var(--text-muted)] hover:text-[var(--error)]"
            >
              ×
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleNew}
          className="ui-btn ui-btn-ghost"
        >
          New
        </button>
        <button
          type="button"
          onClick={onSave}
          className="ui-btn ui-btn-ghost"
        >
          Save
        </button>
        <button
          type="button"
          onClick={onShowTemplates}
          className="ui-btn ui-btn-ghost"
        >
          Templates
        </button>
        <button
          type="button"
          onClick={startReplay}
          disabled={!hasResults || isReplaying}
          title={hasResults ? 'Walk through the pipeline step by step' : 'Run the pipeline first to enable replay'}
          className="ui-btn ui-btn-ghost"
        >
          ▶ Replay
        </button>

        <span className="ui-divider" />

        <button
          type="button"
          onClick={handleExportJson}
          className="ui-btn ui-btn-ghost"
        >
          Export JSON
        </button>
        <button
          type="button"
          onClick={() => importInputRef.current?.click()}
          className="ui-btn ui-btn-ghost"
        >
          Import JSON
        </button>
        <input ref={importInputRef} type="file" accept=".json" className="hidden" onChange={handleImportJson} />

        <span className="ui-divider" />

        {username ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text)]">{username}</span>
            <button
              type="button"
              onClick={clearAuth}
              className="ui-btn ui-btn-ghost"
            >
              Log out
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={onShowAuth}
            className="ui-btn ui-btn-primary"
          >
            Sign In
          </button>
        )}
      </div>
    </header>
  )
}
