import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'

import executionApi from '../../api/executionApi'
import usePipelineStore from '../../store/pipelineStore'
import { getTargetPort } from '../../utils/edgePorts'
import { isChartNode } from '../../utils/chartData'

// Recharts is ~400kB of the bundle and is only needed once someone actually looks at a chart
// node, so it's code-split behind a lazy import. Every other node type — which is most
// sessions, and always the first screen — never downloads it.
const ChartPreview = lazy(() => import('./ChartPreview'))

// Enough room for a header strip plus a chart you can actually read. See the style prop on
// the panel below.
const CHART_MIN_HEIGHT = 320
const PAGE_SIZE = 100

// preview_data is capped at 100 rows per page server-side (PLAN.md §7.3) — no windowing
// library needed on top of that; rendering 100 plain <tr>s is cheap.
export default function DataPreviewTable() {
  const previewNodeId = usePipelineStore((s) => s.previewNodeId)
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const csvData = usePipelineStore((s) => s.csvData)
  // Height is owned by the store so PreviewResizeHandle (which lives in App's layout, between
  // the canvas and this panel) and the panel itself can never disagree about it.
  const previewHeight = usePipelineStore((s) => s.previewHeight)
  const [exportingFormat, setExportingFormat] = useState(null)
  const [page, setPage] = useState(0)
  const [pageRows, setPageRows] = useState(null)
  const [loadingPage, setLoadingPage] = useState(false)
  const pageCacheRef = useRef({})

  const activeNodeId = previewNodeId || selectedNodeId
  const result = activeNodeId ? nodeResults[activeNodeId] : null
  const activeNode = activeNodeId ? nodes.find((n) => n.id === activeNodeId) : null
  // The three chart nodes render as a chart, not a table (PLAN.md §6 — the backend passes
  // their data straight through and the browser does the drawing). The table is still shown
  // underneath: the chart is a view of the same rows, and the export button lives on it.
  const isChart = !!activeNode && isChartNode(activeNode.data.nodeType)

  // Reset pagination to page 1 whenever the active node or its execution result changes.
  useEffect(() => {
    setPage(0)
    setPageRows(null)
    setLoadingPage(false)
    pageCacheRef.current = {}
  }, [activeNodeId, result])

  const totalRows = result?.total_row_count ?? (result?.preview_data?.length || 0)
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE))

  const goToPage = async (nextPage) => {
    if (!activeNodeId || nextPage < 0 || nextPage >= totalPages || nextPage === page) return
    if (nextPage === 0) {
      setPage(0)
      setPageRows(null)
      return
    }
    if (pageCacheRef.current[nextPage]) {
      setPage(nextPage)
      setPageRows(pageCacheRef.current[nextPage])
      return
    }
    setLoadingPage(true)
    try {
      const payload = {
        nodes: nodes.map((n) => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edges.map((e) => ({ source_node_id: e.source, target_node_id: e.target, target_port: getTargetPort(e) })),
        csv_data: csvData || undefined,
        target_node_id: activeNodeId,
        preview_offset: nextPage * PAGE_SIZE,
      }
      const res = await executionApi.post('/api/pipeline/preview', payload)
      const fetched = res.data.node_results?.[activeNodeId]?.preview_data || []
      pageCacheRef.current[nextPage] = fetched
      setPage(nextPage)
      setPageRows(fetched)
    } catch (err) {
      window.alert(`Could not load page ${nextPage + 1}: ${err.response?.data?.detail || 'unknown error'}`)
    } finally {
      setLoadingPage(false)
    }
  }

  const handleExport = async (format = 'csv') => {
    if (!activeNodeId) return
    setExportingFormat(format)
    try {
      const payload = {
        nodes: nodes.map((n) => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edges.map((e) => ({ source_node_id: e.source, target_node_id: e.target, target_port: getTargetPort(e) })),
        csv_data: csvData || undefined,
        target_node_id: activeNodeId,
        export_format: format,
      }
      const res = await executionApi.post('/api/pipeline/export', payload, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeNodeId}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      window.alert(`Export failed: ${err.response?.data?.detail || 'unknown error'}`)
    } finally {
      setExportingFormat(null)
    }
  }
  const rows = page === 0 ? (result?.preview_data || []) : (pageRows || [])
  const startRow = totalRows === 0 || rows.length === 0 ? 0 : page * PAGE_SIZE + 1
  const endRow = page * PAGE_SIZE + rows.length
  const errorRows = useMemo(() => new Set(result?.error_row_indices || []), [result])

  const columnNames = useMemo(() => {
    if (result?.output_schema?.columns?.length) return result.output_schema.columns.map((c) => c.name)
    return rows[0] ? Object.keys(rows[0]) : []
  }, [result, rows])

  const columns = useMemo(
    () =>
      columnNames.map((name) => ({
        // accessorFn, not accessorKey — real column names (from uploaded CSV headers) can
        // contain dots/brackets that accessorKey would otherwise parse as a nested path.
        id: name,
        accessorFn: (row) => row[name],
        header: name,
        cell: (info) => {
          const v = info.getValue()
          return v === null || v === undefined || v === '' ? (
            <span className="italic text-[var(--text-muted)]">null</span>
          ) : (
            String(v)
          )
        },
      })),
    [columnNames]
  )

  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() })

  return (
    // A chart has a height floor of its own: squeezed into the panel's minimum strip it is
    // unreadable, which is the same "why is my chart blank" problem as before. So while a
    // chart node is selected the panel won't go below CHART_MIN_HEIGHT, and it springs back
    // to the dragged size the moment a non-chart node is selected.
    <div
      className="flex shrink-0 flex-col overflow-hidden bg-[var(--panel)]"
      style={{ height: Math.max(previewHeight, isChart ? CHART_MIN_HEIGHT : 0) }}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--panel-alt)] px-3 py-1.5">
        <h3 className="ui-panel-title">Preview</h3>
        {result?.success && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
              {totalRows > 0
                ? `${startRow.toLocaleString()}–${endRow.toLocaleString()} of ${totalRows.toLocaleString()} rows`
                : '0 rows'}
            </span>
            {totalPages > 1 && (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => goToPage(page - 1)}
                  disabled={page === 0 || loadingPage}
                  className="ui-btn ui-btn-default px-2 py-0.5"
                >
                  ‹ Prev
                </button>
                <span className="px-1 text-[10px] tabular-nums text-[var(--text-muted)]">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => goToPage(page + 1)}
                  disabled={page >= totalPages - 1 || loadingPage}
                  className="ui-btn ui-btn-default px-2 py-0.5"
                >
                  Next ›
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={() => handleExport('csv')}
              disabled={!!exportingFormat}
              className="ui-btn ui-btn-default"
            >
              {exportingFormat === 'csv' ? 'Exporting…' : 'Export CSV'}
            </button>
            <button
              type="button"
              onClick={() => handleExport('xlsx')}
              disabled={!!exportingFormat}
              className="ui-btn ui-btn-default"
            >
              {exportingFormat === 'xlsx' ? 'Exporting…' : 'Export XLSX'}
            </button>
          </div>
        )}
      </div>

      <div className={`flex-1 overflow-auto ${isChart ? 'flex flex-col' : ''}`}>
        {!activeNodeId && <p className="p-3 text-xs text-[var(--text-muted)]">Select a node to preview its output.</p>}
        {activeNodeId && !result && <p className="p-3 text-xs text-[var(--text-muted)]">No result yet.</p>}

        {result && !result.success && (
          <div className="p-3 text-xs">
            <p className="font-medium text-[var(--error)]">{result.skipped ? 'Skipped' : 'Error'}</p>
            <p className="mt-0.5 text-[var(--text)]">{result.error_message}</p>
            {result.error_suggestion && (
              <p className="mt-1 text-[var(--text-muted)]">Suggestion: {result.error_suggestion}</p>
            )}
          </div>
        )}

        {result?.success && rows.length === 0 && (
          <p className="p-3 text-xs text-[var(--text-muted)]">This node's output has no rows.</p>
        )}

        {result?.success && rows.length > 0 && (
          <>
            {isChart && (
              <div className="h-64 shrink-0 border-b border-[var(--border-light)]">
                <Suspense
                  fallback={
                    <p className="flex h-full items-center justify-center text-xs text-[var(--text-muted)]">
                      Loading chart…
                    </p>
                  }
                >
                  <ChartPreview
                    nodeType={activeNode.data.nodeType}
                    config={activeNode.data.config || {}}
                    rows={rows}
                  />
                </Suspense>
              </div>
            )}
            <table className="w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-[var(--panel-alt)]">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        className="border-b border-[var(--border)] bg-[var(--panel-alt)] px-2 py-1 font-semibold text-[var(--text-muted)]"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => {
                  const isErrorRow = errorRows.has(page * PAGE_SIZE + row.index)
                  return (
                    <tr
                      key={row.id}
                      className={isErrorRow ? 'bg-[var(--error)]/10' : undefined}
                      title={isErrorRow ? 'This value could not be converted and was left blank' : undefined}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="border-b border-[var(--border-light)] px-2 py-1 text-[var(--text)]">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
