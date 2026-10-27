import { useState } from 'react'
import useTemplates from '../../hooks/useTemplates'
import usePipelineStore from '../../store/pipelineStore'

export default function SaveModal({ onClose, onSaveSuccess }) {
  const { create, update } = useTemplates()
  const currentTemplateId = usePipelineStore((s) => s.currentTemplateId)
  const currentTemplateName = usePipelineStore((s) => s.currentTemplateName)
  const setCurrentTemplate = usePipelineStore((s) => s.setCurrentTemplate)

  const defaultName = currentTemplateName
    ? `${currentTemplateName} (Copy)`
    : 'My Pipeline'

  const [name, setName] = useState(defaultName)
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const handleSaveAsNew = async (e) => {
    e?.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Template name cannot be empty.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const { nodes, edges } = usePipelineStore.getState()
      const pipelineJson = { version: '1.0', nodes, edges }
      const created = await create(trimmed, description.trim() || null, pipelineJson)
      setCurrentTemplate(created.id, created.name)
      onSaveSuccess?.(`Saved new template "${created.name}"`)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not save template.')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateExisting = async (e) => {
    e?.preventDefault()
    if (!currentTemplateId) return
    setSaving(true)
    setError(null)
    try {
      const { nodes, edges } = usePipelineStore.getState()
      const pipelineJson = { version: '1.0', nodes, edges }
      const updatePayload = {
        name: name.trim() || currentTemplateName,
        pipeline_json: pipelineJson,
      }
      if (description.trim()) {
        updatePayload.description = description.trim()
      }
      const updated = await update(currentTemplateId, updatePayload)
      setCurrentTemplate(updated.id, updated.name)
      onSaveSuccess?.(`Updated template "${updated.name}"`)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not update template.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="ui-backdrop" onClick={onClose}>
      <div
        className="ui-modal w-96 p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">Save Pipeline</h2>

        {currentTemplateId && currentTemplateName && (
          <div className="mb-3 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel-alt)] p-2 text-xs text-[var(--text-muted)]">
            Currently loaded template: <strong className="text-[var(--text)]">{currentTemplateName}</strong>
          </div>
        )}

        <form onSubmit={handleSaveAsNew} className="flex flex-col gap-3">
          <div>
            <label className="ui-label" htmlFor="template-name">
              Template Name
            </label>
            <input
              id="template-name"
              type="text"
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Monthly Sales Report"
              className="ui-input"
            />
          </div>

          <div>
            <label className="ui-label" htmlFor="template-desc">
              Description (optional)
            </label>
            <textarea
              id="template-desc"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Notes about this pipeline..."
              className="ui-input resize-none"
            />
          </div>

          {error && <p className="text-xs text-[var(--error)]">{error}</p>}

          {currentTemplateId ? (
            <div className="mt-1 flex flex-col gap-2">
              <button
                type="submit"
                disabled={saving || !name.trim()}
                className="ui-btn ui-btn-primary w-full py-1.5"
              >
                {saving ? 'Saving…' : 'Save as New Template'}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={handleUpdateExisting}
                className="ui-btn ui-btn-default w-full py-1.5"
              >
                {saving ? 'Updating…' : `Update "${currentTemplateName}"`}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="ui-btn ui-btn-ghost w-full py-1.5"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="mt-1 flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="ui-btn ui-btn-ghost flex-1 py-1.5"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || !name.trim()}
                className="ui-btn ui-btn-primary flex-1 py-1.5"
              >
                {saving ? 'Saving…' : 'Save Template'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
