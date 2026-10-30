export default function ColorPickerField({ value, onChange }) {
  return (
    <input
      type="color"
      value={value || '#217346'}
      onChange={(e) => onChange(e.target.value)}
      className="h-7 w-14 cursor-pointer rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)]"
    />
  )
}
