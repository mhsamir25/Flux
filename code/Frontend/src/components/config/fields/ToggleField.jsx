// Not strictly binary — the backend uses TOGGLE for options like
// ASC/DESC (sort's `direction`), each with its own `options` pair. Falls back to a generic
// Off/On pair only if a TOGGLE field somehow has no options.
export default function ToggleField({ field, value, onChange }) {
  const options = field.options?.length ? field.options : ['Off', 'On']
  return (
    <div className="inline-flex overflow-hidden rounded-[var(--radius)] border border-[var(--border)]">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`px-2.5 py-1 text-xs transition-colors ${
            value === opt
              ? 'bg-[var(--accent)] text-[var(--accent-text)]'
              : 'bg-[var(--panel)] text-[var(--text)] hover:bg-[var(--panel-hover)]'
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
