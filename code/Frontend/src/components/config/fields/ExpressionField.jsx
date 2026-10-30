// PLAN.md §5 describes EXPRESSION as "structured operand/operator/operand," but the actual
// backend (add_calculated_column, Phase 5b) parses config["expression"] as a plain string
// through its own recursive-descent parser (e.g. "price * quantity", 'IF(price > 100, price
// * 0.9, price)') — not a structured object. A text input matching that real contract, not
// the plan's more abstract description, is what actually round-trips to a working pipeline.
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
