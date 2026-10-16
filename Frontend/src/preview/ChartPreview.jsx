import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  buildChartData,
  buildSliceColors,
  formatTick,
  getChartSpec,
  isEmptyChartData,
} from '../../utils/chartData'

// Renders one of the three OUTPUT chart nodes from its config + its upstream preview data.
//
// The backend deliberately does no chart work — bar_chart/line_chart/pie_chart are pure
// pass-throughs (PLAN.md §6: "chart rendering happens entirely in the frontend (Recharts)
// using the node's config plus the upstream preview data"). That means everything the chart
// needs is already in hand: the node's x_column/y_column/title/color from the config panel,
// and preview_data from the last execute call. Nothing here calls the API.
//
// The chart type comes from the node's own `type`, never from a config field, so a user can't
// end up with a pie chart's config driving a bar chart. All the fiddly data prep (numeric
// coercion, null handling, pie aggregation) lives in utils/chartData.js so it can be tested
// without a DOM — see chartData.test.js.
export default function ChartPreview({ nodeType, config, rows }) {
  const spec = getChartSpec(nodeType, config, rows)

  if (spec.error) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-xs text-[var(--text-muted)]">
        {spec.error}
      </div>
    )
  }

  const data = buildChartData(spec.kind, rows, spec.xKey, spec.yKey)

  if (isEmptyChartData(data)) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-xs text-[var(--text-muted)]">
        No plottable values in <span className="font-medium text-[var(--text)]">{spec.yKey}</span> — every
        row is blank there, so there is nothing to draw.
      </div>
    )
  }

  const common = {
    data,
    margin: { top: 8, right: 12, bottom: 4, left: 4 },
  }

  return (
    // min-h-[200px] rather than min-h-0: ResponsiveContainer measures its parent and renders
    // nothing at all when that measurement is 0, and `min-h-0` explicitly permits a flex
    // child to collapse to zero. A floor of 200px means the chart always has room, and in the
    // app (a 256px-tall slot) the floor is never the binding constraint.
    <div className="flex h-full w-full flex-col">
      {spec.title && (
        <p className="shrink-0 px-3 pt-2 text-xs font-medium text-[var(--text)]">{spec.title}</p>
      )}
      <div className="min-h-[200px] flex-1 p-2">
        <ResponsiveContainer width="100%" height="100%">
          {spec.kind === 'pie' ? (
            <PieChart {...common}>
              <Pie
                data={data}
                dataKey="y"
                nameKey="label"
                // Every slice needs room for a label; a pie of 40 rows is unreadable either
                // way, so the outer radius is capped rather than left to overflow.
                outerRadius="72%"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {data.map((entry, index) => (
                  <Cell key={entry.label} fill={buildSliceColors(data.length, spec.color)[index]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => [Number(value).toLocaleString(), spec.yKey]}
                labelFormatter={(label) => String(label)}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          ) : spec.kind === 'line' ? (
            <LineChart {...common}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="x"
                tickFormatter={(v) => formatTick(v)}
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                stroke="var(--border)"
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                stroke="var(--border)"
                width={56}
              />
              <Tooltip
                formatter={(value) =>
                  value === null || value === undefined
                    ? ['—', spec.yKey]
                    : [Number(value).toLocaleString(), spec.yKey]
                }
                labelFormatter={(label) => String(label)}
              />
              {/* connectNulls=false so a row convert_type blanked to null shows as a gap
                  rather than a straight line drawn through data that isn't there. */}
              <Line
                type="monotone"
                dataKey="y"
                name={spec.yKey}
                stroke={spec.color}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          ) : (
            <BarChart {...common}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="x"
                tickFormatter={(v) => formatTick(v)}
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                stroke="var(--border)"
                interval={0}
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                stroke="var(--border)"
                width={56}
              />
              <Tooltip
                cursor={{ fill: 'var(--panel-hover)' }}
                formatter={(value) =>
                  value === null || value === undefined
                    ? ['—', spec.yKey]
                    : [Number(value).toLocaleString(), spec.yKey]
                }
                labelFormatter={(label) => String(label)}
              />
              <Bar dataKey="y" name={spec.yKey} fill={spec.color} isAnimationActive={false} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
