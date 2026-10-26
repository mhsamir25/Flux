
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  aggregateByLabel,
  buildChartData,
  buildChartPoints,
  buildSliceColors,
  formatTick,
  getChartKind,
  getChartSpec,
  isChartNode,
  isEmptyChartData,
} from './chartData.js'

const ROWS = [
  { subject: 'Math', score_average: 90 },
  { subject: 'Science', score_average: 62.5 },
  { subject: null, score_average: 77 },
]



test('only the three chart node types are chart nodes', () => {
  assert.equal(isChartNode('bar_chart'), true)
  assert.equal(isChartNode('line_chart'), true)
  assert.equal(isChartNode('pie_chart'), true)
})

test('every other node type is explicitly not a chart', () => {
 
  for (const type of ['data_table', 'read_csv', 'filter', 'group_by_aggregate', 'join', 'pivot']) {
    assert.equal(isChartNode(type), false, `${type} should not be a chart`)
    assert.equal(getChartKind(type), null)
  }
})

test('chart kind maps to the right recharts chart', () => {
  assert.equal(getChartKind('bar_chart'), 'bar')
  assert.equal(getChartKind('line_chart'), 'line')
  assert.equal(getChartKind('pie_chart'), 'pie')
})

// --- spec resolution ----------------------------------------------------------------

test('a fully configured node resolves to a usable spec', () => {
  const spec = getChartSpec(
    'bar_chart',
    { x_column: 'subject', y_column: 'score_average', title: 'Averages', color: '#123456' },
    ROWS
  )
  assert.equal(spec.error, undefined)
  assert.deepEqual(
    { kind: spec.kind, xKey: spec.xKey, yKey: spec.yKey, title: spec.title, color: spec.color },
    { kind: 'bar', xKey: 'subject', yKey: 'score_average', title: 'Averages', color: '#123456' }
  )
})

test('title and color are optional and fall back', () => {
  const spec = getChartSpec('pie_chart', { x_column: 'subject', y_column: 'score_average' }, ROWS)
  assert.equal(spec.title, '')
  assert.match(spec.color, /^#[0-9a-f]{6}$/i)
})

test('a node with no columns selected explains what to do', () => {
  const spec = getChartSpec('bar_chart', {}, ROWS)
  assert.match(spec.error, /X and a Y column/)
  assert.equal(spec.kind, undefined)
})

test('a half-configured node is also rejected', () => {
  const spec = getChartSpec('line_chart', { x_column: 'subject' }, ROWS)
  assert.match(spec.error, /X and a Y column/)
})

test('a column that is not in the output is reported, naming what is available', () => {
  // The exact mistake after a group_by_aggregate: 'score' became 'score_average'.
  const spec = getChartSpec(
    'bar_chart',
    { x_column: 'subject', y_column: 'score' },
    [{ subject: 'Math', score_average: 90 }]
  )
  assert.match(spec.error, /‘score’ is not in this node’s output/)
  assert.match(spec.error, /Available: subject, score_average/)
})

test('both missing columns are named', () => {
  const spec = getChartSpec('bar_chart', { x_column: 'a', y_column: 'b' }, [{ c: 1 }])
  assert.match(spec.error, /‘a’ and ‘b’/)
  assert.match(spec.error, /are not in/)
})

test('a non-chart node is refused', () => {
  assert.match(getChartSpec('data_table', { x_column: 'a', y_column: 'b' }, ROWS).error, /not a chart/)
})

// --- point building -------------------------------------------------------------------

test('points are built in row order with coerced numbers', () => {
  assert.deepEqual(buildChartPoints(ROWS, 'subject', 'score_average'), [
    { x: 'Math', y: 90, label: 'Math' },
    { x: 'Science', y: 62.5, label: 'Science' },
    { x: '(blank)', y: 77, label: '(blank)' },
  ])
})

test('numeric strings from the JSON response are coerced', () => {
  // preview_data is JSON, so a NUMBER column can arrive as "85" if it round-tripped oddly.
  const points = buildChartPoints([{ a: 'x', v: '85' }, { a: 'y', v: '1,234' }], 'a', 'v')
  assert.deepEqual(points.map((p) => p.y), [85, 1234])
})

test('unparseable values become null rather than NaN', () => {
  // A NaN here would poison the chart's Y domain and squash every real bar to nothing.
  const points = buildChartPoints([{ a: 'x', v: 'n/a' }, { a: 'y', v: null }, { a: 'z', v: '' }], 'a', 'v')
  assert.deepEqual(points.map((p) => p.y), [null, null, null])
})

test('a missing column entirely yields nulls, not crashes', () => {
  const points = buildChartPoints([{ a: 'x' }], 'a', 'nope')
  assert.deepEqual(points, [{ x: 'x', y: null, label: 'x' }])
})

test('null and undefined x values get a readable label', () => {
  const points = buildChartPoints([{ a: null, v: 1 }, { v: 2 }], 'a', 'v')
  assert.deepEqual(points.map((p) => p.label), ['(blank)', '(blank)'])
})

test('empty and missing inputs do not throw', () => {
  assert.deepEqual(buildChartPoints([], 'a', 'b'), [])
  assert.deepEqual(buildChartPoints(undefined, 'a', 'b'), [])
  assert.deepEqual(buildChartPoints([{ a: 'x', v: 1 }], undefined, undefined), [
    { x: '(blank)', y: null, label: '(blank)' },
  ])
})

// --- pie aggregation -------------------------------------------------------------------

test('duplicate labels are summed for a pie', () => {
 
  const rows = [
    { region: 'North', revenue: 10 },
    { region: 'South', revenue: 30 },
    { region: 'North', revenue: 5 },
  ]
  assert.deepEqual(buildChartData('pie', rows, 'region', 'revenue'), [
    { x: 'North', label: 'North', y: 15 },
    { x: 'South', label: 'South', y: 30 },
  ])
})

test('bar and line charts keep every row in order, duplicates included', () => {
  const rows = [
    { m: 'Jan', v: 1 },
    { m: 'Feb', v: 2 },
    { m: 'Jan', v: 3 },
  ]
  assert.deepEqual(buildChartData('bar', rows, 'm', 'v').map((p) => p.y), [1, 2, 3])
  assert.deepEqual(buildChartData('line', rows, 'm', 'v').map((p) => p.y), [1, 2, 3])
})

test('a label with only unreadable values is dropped, not shown as a 0% slice', () => {
  // "Apr 0%" would imply a measured zero; the column was actually blank.
  assert.deepEqual(aggregateByLabel([{ label: 'a', y: null }, { label: 'b', y: 5 }]), [
    { x: 'b', label: 'b', y: 5 },
  ])
  assert.deepEqual(aggregateByLabel([{ label: 'a', y: null }, { label: 'a', y: null }]), [])
})

test('a genuine zero is kept and nulls alongside it are skipped', () => {
  assert.deepEqual(aggregateByLabel([{ label: 'a', y: null }, { label: 'a', y: 5 }, { label: 'b', y: 0 }]), [
    { x: 'a', label: 'a', y: 5 },
    { x: 'b', label: 'b', y: 0 },
  ])
})

// --- emptiness + colours + ticks ---------------------------------------------------------

test('emptiness is detected for no rows, no data, and all-unreadable data', () => {
  assert.equal(isEmptyChartData([]), true)
  assert.equal(isEmptyChartData(null), true)
  assert.equal(isEmptyChartData(buildChartPoints([{ a: 'x', v: 'nope' }], 'a', 'v')), true)
  assert.equal(isEmptyChartData(buildChartPoints([{ a: 'x', v: 1 }], 'a', 'v')), false)
})

test('slice colours lead with the node colour then cycle the palette', () => {
  const colors = buildSliceColors(4, '#abcdef')
  assert.equal(colors[0], '#abcdef')
  assert.equal(colors.length, 4)
  assert.equal(new Set(colors).size, 4, 'slices should be visually distinct')
})

test('long tick labels are truncated so the axis stays readable', () => {
  assert.equal(formatTick('Math'), 'Math')
  assert.equal(formatTick('a'.repeat(40)).length, 18)
  assert.ok(formatTick('a'.repeat(40)).endsWith('…'))
  assert.equal(formatTick(null), '')
})
