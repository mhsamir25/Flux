import ColumnSelectField from './fields/ColumnSelectField'
import MultiColumnSelectField from './fields/MultiColumnSelectField'
import TextField from './fields/TextField'
import NumberField from './fields/NumberField'
import EnumField from './fields/EnumField'
import ToggleField from './fields/ToggleField'
import ColorPickerField from './fields/ColorPickerField'
import ExpressionField from './fields/ExpressionField'
import MappingsField from './fields/MappingsField'
import AggregationsField from './fields/AggregationsField'

const RENDERERS = {
  COLUMN_SELECT: ColumnSelectField,
  MULTI_COLUMN_SELECT: MultiColumnSelectField,
  TEXT: TextField,
  NUMBER: NumberField,
  ENUM: EnumField,
  TOGGLE: ToggleField,
  COLOR_PICKER: ColorPickerField,
  EXPRESSION: ExpressionField,
}


const STRUCTURAL_RENDERERS = {
  mappings: MappingsField,
  aggregations: AggregationsField,
}

export default function FieldRenderer({ field, value, onChange, columns }) {
  const Structural = STRUCTURAL_RENDERERS[field.key]
  if (Structural) return <Structural value={value} onChange={onChange} columns={columns} />

  const Renderer = RENDERERS[field.type]
  if (!Renderer) return <p className="text-xs text-[var(--error)]">Unknown field type: {field.type}</p>

  return <Renderer field={field} value={value} onChange={onChange} columns={columns} />
}
