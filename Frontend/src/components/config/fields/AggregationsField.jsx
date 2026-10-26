
const FUNCTIONS = ['SUM', 'AVERAGE', 'COUNT', 'MIN', 'MAX', 'COUNT_DISTINCT']
const rowInput = 'ui-input flex-1'

export default function AggregationsField({ value, onChange, columns }) {
  const aggregations = Array.isArray(value) ? value : []

  const update = (idx, key, val) => onChange(aggregations.map((a, i) => (i === idx ? { ...a, [key]: val } : a)))
  const remove = (idx) => onChange(aggregations.filter((_, i) => i !== idx))
  const add = () => onChange([...aggregations, { column: '', function: 'SUM' }])

  return (
    <div className="flex flex-col gap-1.5">
      {aggregations.map((a, idx) => (
        <div key={idx} className="flex items-center gap-1">
          <select value={a.column || ''} onChange={(e) => update(idx, 'column', e.target.value)} className={rowInput}>
            <option value="">column…</option>
            {columns.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
          <select value={a.function || 'SUM'} onChange={(e) => update(idx, 'function', e.target.value)} className="ui-input w-28">
            {FUNCTIONS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
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
        + Add aggregation
      </button>
    </div>
  )
}
