const inputClass = 'ui-input'

export default function ColumnSelectField({ value, onChange, columns }) {
  return (
    <select value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)} className={inputClass}>
      <option value="">{columns.length ? 'Select a column…' : 'No columns available yet'}</option>
      {columns.map((c) => (
        <option key={c.name} value={c.name}>
          {c.name}
        </option>
      ))}
    </select>
  )
}
