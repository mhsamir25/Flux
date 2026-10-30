export default function TextField({ field, value, onChange }) {
  return (
    <input
      type="text"
      value={value ?? ''}
      placeholder={field.placeholder || ''}
      onChange={(e) => onChange(e.target.value)}
      className="ui-input"
    />
  )
}
