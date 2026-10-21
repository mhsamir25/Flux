import { useEffect } from 'react'

import useAuth from '../../hooks/useAuth'
import useTemplates from '../../hooks/useTemplates'
import usePipelineStore from '../../store/pipelineStore'


export default function TemplateBrowser({ onClose, onRequestAuth }) {
  const { isGuest } = useAuth()
  const { templates, loading, error, list, remove } = useTemplates()
  const loadPipeline = usePipelineStore((s) => s.loadPipeline)
  const setCurrentTemplateId = usePipelineStore((s) => s.setCurrentTemplateId)

  useEffect(() => {
    if (!isGuest) list()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isGuest])

  const handleLoad = (template) => {
    const { nodes, edges } = template.pipeline_json || {}
    loadPipeline(nodes || [], edges || [])
    setCurrentTemplateId(template.id)
    onClose()
  }

  const handleDelete = async (e, id) => {
    e.stopPropagation()
    if (!window.confirm('Delete this template? This cannot be undone.')) return
    await remove(id)
  }

  return (
    <div className="ui-backdrop" onClick={onClose}>
      <div
        className="ui-modal max-h-[70vh] w-96 overflow-y-auto p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">Templates</h2>

        {isGuest ? (
          <div className="text-xs text-[var(--text-muted)]">
            <p className="mb-3">Sign in to save and load pipelines.</p>
            <button
              type="button"
              onClick={() => {
                onClose()
                onRequestAuth?.()
              }}
              className="ui-btn ui-btn-primary w-full py-1.5"
            >
              Sign In
            </button>
          </div>
        ) : (
          <>
            {loading && <p className="text-xs text-[var(--text-muted)]">Loading…</p>}
            {error && <p className="text-xs text-[var(--error)]">{error}</p>}
            {!loading && !error && templates.length === 0 && (
              <p className="text-xs text-[var(--text-muted)]">No saved pipelines yet. Build one and click Save.</p>
            )}
            <div className="flex flex-col gap-1">
              {templates.map((t) => (
                <div
                  key={t.id}
                  onClick={() => handleLoad(t)}
                  className="flex cursor-pointer items-center justify-between rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] px-2 py-1.5 text-xs hover:bg-[var(--panel-hover)]"
                >
                  <div>
                    <div className="font-medium text-[var(--text)]">{t.name}</div>
                    <div className="text-[10px] text-[var(--text-muted)]">
                      {new Date(t.updated_at).toLocaleString()}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDelete(e, t.id)}
                    className="shrink-0 text-[var(--text-muted)] hover:text-[var(--error)]"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        <button
          type="button"
          onClick={onClose}
          className="ui-btn ui-btn-default mt-4 w-full py-1.5"
        >
          Close
        </button>
      </div>
    </div>
  )
}
