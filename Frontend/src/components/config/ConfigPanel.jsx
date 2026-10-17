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
  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const updateNodeConfig = usePipelineStore((s) => s.updateNodeConfig)
  const collapsed = usePipelineStore((s) => s.configPanelCollapsed)
  const toggleConfigPanel = usePipelineStore((s) => s.toggleConfigPanel)

  const selectedNode = nodes.find((n) => n.id === selectedNodeId)
  const catalogueEntry = selectedNode && nodeCatalogue.find((c) => c.id === selectedNode.data.nodeType)

  // No node selected means there is nothing to configure, so the panel gives its width back
  // to the canvas instead of sitting there showing "select a node". A manual collapse is
  // sticky even with a node selected — if someone folds it to get at the canvas, it should
  // stay folded until they ask for it back.
  //
  // Renders nothing when closed: the reopen affordance (a slim full-height tab) is drawn by
  // App.jsx *outside* this column, beside the canvas overview, so the tab doesn't have to be
  // stacked above the minimap in here.
  if (!selectedNode || collapsed) return null

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
            attach real data via the upload zone above the canvas.
          </p>
        )}

        {catalogueEntry?.config_schema.length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">This node has no configuration.</p>
        )}

        <div className="flex flex-col gap-3">
          {catalogueEntry?.config_schema.map((field) => {
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
      </div>
    </aside>
  )
}
