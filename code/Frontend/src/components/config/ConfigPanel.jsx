import usePipelineStore from '../../store/pipelineStore'
import { getTargetPort } from '../../utils/edgePorts'
import FieldRenderer from './FieldRenderer'
// Finds the columns available to a config field: walk back to whichever upstream node feeds
// the given port (null for the single-input case, 'left'/'right' for join) and read its last
// execution's output_schema. Empty until that upstream node has actually run successfully —
// there's no other source of "what columns exist" once a node isn't itself a source.
function upstreamColumns(nodeId, edges, nodeResults, port) {
  const edge = edges.find((e) => e.target === nodeId && getTargetPort(e) === port)
  if (!edge) return []
  const result = nodeResults[edge.source]
  return result?.success ? result.output_schema?.columns || [] : []
}

export default function ConfigPanel() {
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const selectedNodeIds = usePipelineStore((s) => s.selectedNodeIds)
  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const updateNodeConfig = usePipelineStore((s) => s.updateNodeConfig)
  const deleteSelectedNodes = usePipelineStore((s) => s.deleteSelectedNodes)
  const deleteNode = usePipelineStore((s) => s.deleteNode)
  const clearSelection = usePipelineStore((s) => s.clearSelection)
  const collapsed = usePipelineStore((s) => s.configPanelCollapsed)
  const toggleConfigPanel = usePipelineStore((s) => s.toggleConfigPanel)

  const multiSelected = selectedNodeIds && selectedNodeIds.length > 1
  const selectedNode = nodes.find((n) => n.id === selectedNodeId)
  const catalogueEntry = selectedNode && nodeCatalogue.find((c) => c.id === selectedNode.data.nodeType)

  if (collapsed) return null

  // If multiple nodes are selected, show multi-selection management panel
  if (multiSelected) {
    const multiNodes = nodes.filter((n) => selectedNodeIds.includes(n.id))
    return (
      <aside className="flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[var(--panel)]">
        <div className="flex shrink-0 items-center justify-between px-3 pb-1 pt-3">
          <h3 className="ui-panel-title">Selection</h3>
          <button
            type="button"
            onClick={toggleConfigPanel}
            title="Collapse panel"
            aria-label="Collapse panel"
            className="ui-btn ui-btn-ghost px-1.5 py-0.5"
          >
            »
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col justify-between overflow-y-auto px-3 pb-3">
          <div className="flex flex-col gap-3">
            <div>
              <div className="text-sm font-medium text-[var(--text)]">{multiNodes.length} Nodes Selected</div>
              <div className="mt-0.5 text-xs text-[var(--text-muted)]">Multiple nodes selected on canvas</div>
            </div>

            <div className="flex max-h-56 flex-col gap-1.5 overflow-y-auto rounded-[var(--radius)] border border-[var(--border-light)] bg-[var(--panel-alt)] p-2">
              {multiNodes.map((node) => (
                <div
                  key={node.id}
                  className="flex items-center justify-between rounded border border-[var(--border-light)] bg-[var(--panel)] px-2 py-1 text-xs"
                >
                  <span className="truncate font-medium text-[var(--text)]">{node.data?.displayName || node.id}</span>
                  <span className="text-[10px] uppercase text-[var(--text-muted)]">{node.data?.nodeType}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-2 border-t border-[var(--border-light)] pt-3">
            <button
              type="button"
              onClick={deleteSelectedNodes}
              className="ui-btn flex w-full items-center justify-center gap-1.5 border-[var(--border)] py-1.5 text-[var(--error)] hover:border-[var(--error)]/40 hover:bg-[var(--error)]/10"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              <span>Delete {multiNodes.length} Nodes</span>
            </button>
            <button
              type="button"
              onClick={clearSelection}
              className="ui-btn ui-btn-ghost w-full py-1 text-xs"
            >
              Deselect All
            </button>
          </div>
        </div>
      </aside>
    )
  }

  // No node selected means there is nothing to configure
  if (!selectedNode) return null

  return (
    // flex-1 + min-h-0: the panel takes whatever height the column has left above the canvas
    // overview pinned below it, and scrolls internally when the form is long (join,
    // group_by_aggregate) instead of pushing the minimap off the bottom.
    <aside className="flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[var(--panel)]">
      <div className="flex shrink-0 items-center justify-between px-3 pb-1 pt-3">
        <h3 className="ui-panel-title">Configuration</h3>
        <button
          type="button"
          onClick={toggleConfigPanel}
          title="Collapse configuration"
          aria-label="Collapse configuration"
          className="ui-btn ui-btn-ghost px-1.5 py-0.5"
        >
          »
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        <div className="mb-3 text-sm font-medium text-[var(--text)]">{selectedNode.data.displayName}</div>

        {selectedNode.data.config?._source_range && (
          <p className="mb-3 rounded-[var(--radius)] border border-[var(--border-light)] bg-[var(--panel-alt)] px-2 py-1.5 text-[10px] text-[var(--text-muted)]">
            Reverse-parsed from <code className="text-[var(--text)]">{selectedNode.data.config._source_range}</code> —
            attach real data via the Read CSV / Read XLSX buttons in the sidebar.
          </p>
        )}

        {catalogueEntry?.config_schema.length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">This node has no configuration.</p>
        )}

        <div className="flex flex-col gap-3">
          {catalogueEntry?.config_schema
            ?.filter((field) => !(selectedNode.data.nodeType === 'filter' && field.key === 'logic'))
            .map((field) => {
            // join's left_key/right_key each pull columns from a different upstream port;
            // every other single-input node's fields all read from the one unnamed port.
            const port = field.key === 'right_key' ? 'right' : field.key === 'left_key' ? 'left' : null
            const columns = upstreamColumns(selectedNode.id, edges, nodeResults, port)
            const config = selectedNode.data.config || {}

            return (
              <div key={field.key}>
                <label className="ui-label">
                  {field.label}
                  {field.required && <span className="text-[var(--error)]"> *</span>}
                </label>
                <FieldRenderer
                  field={field}
                  value={config[field.key]}
                  columns={columns}
                  onChange={(v) => updateNodeConfig(selectedNode.id, { [field.key]: v })}
                />
              </div>
            )
          })}
        </div>

        <div className="mt-6 border-t border-[var(--border-light)] pt-3">
          <button
            type="button"
            onClick={() => deleteNode(selectedNode.id)}
            className="ui-btn ui-btn-ghost w-full py-1 text-xs text-[var(--error)] hover:bg-[var(--error)]/10"
          >
            Delete this node
          </button>
        </div>
      </div>
    </aside>
  )
}
