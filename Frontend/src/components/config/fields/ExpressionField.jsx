
export default function ExpressionField({ field, value, onChange, columns }) {
  return (
    <div>
      <textarea
        value={value ?? ''}
        placeholder={field.placeholder || 'e.g. price * quantity + 10'}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
        className="ui-input resize-y font-mono"
      />
      {columns.length > 0 && (
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">
          Columns: {columns.map((c) => `[${c.name}]`).join(', ')}
        </p>
      )}
    </div>
  )
}
