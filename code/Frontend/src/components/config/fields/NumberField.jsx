export default function NumberField({ field, value, onChange }) {
  return (
    <input
      type="number"
      value={value ?? ''}
      placeholder={field.placeholder || ''}
      onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
      className="ui-input"
    />
  )
}
