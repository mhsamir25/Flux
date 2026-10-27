// Chart data preparation — pure functions, no React and no Recharts imports.
//
// Split out from ChartPreview.jsx so the fiddly part (deciding whether a node is chartable,
// coercing preview_data's loosely-typed cells into plottable points) is unit-testable on its
// own. See chartData.test.js, run with `node --test` from the Frontend directory.
//
// Why this needs care at all: preview_data is JSON decoded by axios, so every cell arrives as
// a string, a number, or null, with no type information — the schema says a column is NUMBER
// but a null in it comes through as null, not as a typed empty. Recharts silently drops or
// mis-renders non-numeric Y values, so numeric coercion happens here, once, and anything that
// genuinely can't be plotted is turned into a null the chart can gap over rather than a NaN
// that corrupts the domain.

export const CHART_NODE_TYPES = {
  bar_chart: 'bar',
  line_chart: 'line',
  pie_chart: 'pie',
}

export function getChartKind(nodeType) {
  return CHART_NODE_TYPES[nodeType] ?? null
}

export function isChartNode(nodeType) {
  return getChartKind(nodeType) !== null
}

// A palette for pie slices and for multi-series cases. The node's own `color` config is a
// single value and is used for bar/line; a pie needs one colour per slice, so it falls back
// to this list (the node's colour first, so a user who picked purple still gets purple-ish
// leading slices).
const SLICE_COLORS = [
  '#7c3aed', '#0ea5e9', '#16a34a', '#f59e0b', '#ef4444',
  '#14b8a6', '#ec4899', '#8b5cf6', '#84cc16', '#f97316',
]

/**
 * Decide whether a node can be charted, and with which columns.
 * Returns { kind, xKey, yKey, title, color, error } — exactly one of `error` / a usable spec.
 */
export function getChartSpec(nodeType, config = {}, rows = []) {
  const kind = getChartKind(nodeType)
  if (!kind) return { error: 'This node is not a chart node.' }

  const { x_column: xKey, y_column: yKey } = config
  if (!xKey || !yKey) {
    return {
      error:
        'Pick an X and a Y column in this node’s configuration to draw the chart. ' +
        'The chart is drawn from the node’s own columns — nothing to plot yet.',
    }
  }

  // Validate against the real data, not just the config: a column can be selected and then
  // disappear upstream (e.g. group_by_aggregate renames score -> score_average), and the
  // backend passes such a node through as a success. Without this check the chart renders an
  // empty frame with no explanation.
  const available = Object.keys(rows[0] ?? {})
  if (rows.length > 0) {
    const missing = [xKey, yKey].filter((key) => !available.includes(key))
    if (missing.length > 0) {
      return {
        error:
          `Column${missing.length > 1 ? 's' : ''} ${missing.map((m) => `‘${m}’`).join(' and ')} ` +
          `${missing.length > 1 ? 'are' : 'is'} not in this node’s output. ` +
          `Available: ${available.join(', ')}.`,
      }
    }
  }

  return {
    kind,
    xKey,
    yKey,
    title: config.title || '',
    color: config.color || SLICE_COLORS[0],
  }
}

/** Coerce a preview cell to a finite number, or null when it isn't one. */
function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  // Strip thousands separators and trailing units-ish whitespace; reject the rest. Note that
  // Number('') === 0, which is why the empty string is handled above rather than here.
  const cleaned = String(value).replace(/,/g, '').trim()
  if (cleaned === '') return null
  const parsed = Number(cleaned)
  return Number.isFinite(parsed) ? parsed : null
}

function toLabel(value) {
  if (value === null || value === undefined || value === '') return '(blank)'
  return String(value)
}

/**
 * Turn preview_data into plottable points: [{ x, y, label }].
 * Rows whose Y can't be read as a number are kept with y = null so the table underneath stays
 * complete; bar/line charts gap over them instead of plotting a fabricated 0.
 */
export function buildChartPoints(rows, xKey, yKey) {
  return (rows ?? []).map((row) => ({
    x: toLabel(row?.[xKey]),
    y: toNumber(row?.[yKey]),
    label: toLabel(row?.[xKey]),
  }))
}

/**
 * Collapse points that share an X label by summing their Y.
 * A pie needs one slice per label; without this, a duplicated category (very common straight
 * out of a raw CSV) produces several identically-named slices and an unreadable legend.
 *
 * Labels whose values are ALL unreadable are dropped rather than summed to zero: a slice
 * labelled "Apr 0%" implies a measured zero, when in fact the column was blank and there is
 * nothing to show. A genuine 0 is kept — only nulls are skipped.
 */
export function aggregateByLabel(points) {
  const totals = new Map()
  points.forEach((point) => {
    if (point.y === null) return
    totals.set(point.label, (totals.get(point.label) ?? 0) + point.y)
  })
  return [...totals.entries()].map(([label, y]) => ({ x: label, label, y }))
}

/** Full dataset for a chart kind: pie charts aggregate, bar/line keep every row in order. */
export function buildChartData(kind, rows, xKey, yKey) {
  const points = buildChartPoints(rows, xKey, yKey)
  return kind === 'pie' ? aggregateByLabel(points) : points
}

/** Slice colours for a pie — the node's colour first, then the palette. */
export function buildSliceColors(count, baseColor) {
  return Array.from({ length: count }, (_, i) =>
    i === 0 ? baseColor : SLICE_COLORS[(i + 1) % SLICE_COLORS.length]
  )
}

/** True when nothing in the dataset can actually be plotted. */
export function isEmptyChartData(data) {
  return !data || data.length === 0 || data.every((point) => point.y === null)
}

/** Compact axis tick label, so long category names don't overlap into mush. */
export function formatTick(value, maxLength = 18) {
  const text = String(value ?? '')
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text
}
