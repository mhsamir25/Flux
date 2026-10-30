// rename_column's config["mappings"] is a list of {from, to} pairs — structurally a list, not
// a flat field, so it's declared with a nominal FieldType (TEXT) on the backend and rendered
// with this dedicated sub-form instead (PLAN.md §13).
const rowInput = 'ui-input min-w-0 flex-1'

export default function MappingsField({ value, onChange, columns }) {
  const mappings = Array.isArray(value) ? value : []

  const update = (idx, key, val) => onChange(mappings.map((m, i) => (i === idx ? { ...m, [key]: val } : m)))
  const remove = (idx) => onChange(mappings.filter((_, i) => i !== idx))
  const add = () => onChange([...mappings, { from: '', to: '' }])

  return (
    <div className="flex flex-col gap-1.5">
      {mappings.map((m, idx) => (
        <div key={idx} className="flex items-center gap-1">
          <select value={m.from || ''} onChange={(e) => update(idx, 'from', e.target.value)} className={rowInput}>
            <option value="">from…</option>
            {columns.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
          <span className="text-xs text-[var(--text-muted)]">→</span>
          <input
            type="text"
            value={m.to || ''}
            placeholder="new name"
            onChange={(e) => update(idx, 'to', e.target.value)}
            className={rowInput}
          />
          <button type="button" onClick={() => remove(idx)} className="text-[var(--text-muted)] hover:text-[var(--error)]">
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        className="ui-btn ui-btn-default self-start border-dashed"
      >
        + Add mapping
      </button>
    </div>
  )
}
