import { lazy, Suspense, useMemo, useState } from 'react'
import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'

import executionApi from '../../api/executionApi'
import usePipelineStore from '../../store/pipelineStore'
import { getTargetPort } from '../../utils/edgePorts'
import { isChartNode } from '../../utils/chartData'


const ChartPreview = lazy(() => import('./ChartPreview'))


const CHART_MIN_HEIGHT = 320


export default function DataPreviewTable() {
  const previewNodeId = usePipelineStore((s) => s.previewNodeId)
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const csvData = usePipelineStore((s) => s.csvData)

  const previewHeight = usePipelineStore((s) => s.previewHeight)
  const [exporting, setExporting] = useState(false)

  const activeNodeId = previewNodeId || selectedNodeId
  const result = activeNodeId ? nodeResults[activeNodeId] : null
  const activeNode = activeNodeId ? nodes.find((n) => n.id === activeNodeId) : null
  
  const isChart = !!activeNode && isChartNode(activeNode.data.nodeType)

  const handleExport = async () => {
    if (!activeNodeId) return
    setExporting(true)
    try {
      const payload = {
        nodes: nodes.map((n) => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edges.map((e) => ({ source_node_id: e.source, target_node_id: e.target, target_port: getTargetPort(e) })),
        csv_data: csvData || undefined,
        target_node_id: activeNodeId,
      }
      const res = await executionApi.post('/api/pipeline/export', payload, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeNodeId}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      window.alert(`Export failed: ${err.response?.data?.detail || 'unknown error'}`)
    } finally {
      setExporting(false)
    }
  }
  const rows = result?.preview_data || []
  const errorRows = useMemo(() => new Set(result?.error_row_indices || []), [result])

  const columnNames = useMemo(() => {
    if (result?.output_schema?.columns?.length) return result.output_schema.columns.map((c) => c.name)
    return rows[0] ? Object.keys(rows[0]) : []
  }, [result, rows])

  const columns = useMemo(
    () =>
      columnNames.map((name) => ({
       
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
   
    <div
      className="flex shrink-0 flex-col overflow-hidden bg-[var(--panel)]"
      style={{ height: Math.max(previewHeight, isChart ? CHART_MIN_HEIGHT : 0) }}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--panel-alt)] px-3 py-1.5">
        <h3 className="ui-panel-title">Preview</h3>
        {result?.success && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[var(--text-muted)]">
              {rows.length.toLocaleString()} of {(result.total_row_count ?? rows.length).toLocaleString()} rows
            </span>
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="ui-btn ui-btn-default"
            >
              {exporting ? 'Exporting…' : 'Export CSV'}
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
                  const isErrorRow = errorRows.has(row.index)
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
