export default function MultiColumnSelectField({ value, onChange, columns }) {
  const selected = Array.isArray(value) ? value : []
  const toggle = (name) => {
    onChange(selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name])
  }

  if (columns.length === 0) {
    return <p className="text-xs text-[var(--text-muted)]">No columns available yet</p>
  }

  return (
    <div className="flex max-h-32 flex-col gap-1 overflow-y-auto rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] p-1.5">
      {columns.map((c) => (
        <label key={c.name} className="flex items-center gap-1.5 text-xs text-[var(--text)]">
          <input
            type="checkbox"
            checked={selected.includes(c.name)}
            onChange={() => toggle(c.name)}
            className="accent-[var(--accent)]"
          />
          {c.name}
        </label>
      ))}
    </div>
  )
}
