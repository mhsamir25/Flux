import { Handle, Position } from '@xyflow/react'

import usePipelineStore from '../../store/pipelineStore'

const CATEGORY_COLOR = {
  SOURCE: 'var(--cat-source)',
  TRANSFORM: 'var(--cat-transform)',
  AGGREGATE: 'var(--cat-aggregate)',
  JOIN: 'var(--cat-join)',
  OUTPUT: 'var(--cat-output)',
}

// One node component for every category (PLAN.md §13: "schema-driven design means most nodes
// differ only in label/icon/color") — input_ports/output_ports and category come entirely
// from the node catalogue (GET /api/nodes), never hardcoded per node type here.
export default function FluxNode({ id, data, selected }) {
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const nodeResults = usePipelineStore((s) => s.nodeResults)
  const isExecuting = usePipelineStore((s) => s.isExecuting)
  const replayNodes = usePipelineStore((s) => s.replayNodes)
  const replayIndex = usePipelineStore((s) => s.replayIndex)

  const catalogueEntry = nodeCatalogue.find((c) => c.id === data.nodeType)
  const category = catalogueEntry?.category || 'TRANSFORM'
  const inputPorts = catalogueEntry?.input_ports ?? 1
  const color = CATEGORY_COLOR[category] || 'var(--text-muted)'
  const result = nodeResults[id]

  const status = result ? (result.skipped ? 'skipped' : result.success ? 'success' : 'error') : null

  // Replay walks replayNodes (the topological execution order, computed once by
  // startReplay()) one step at a time. A node absent from that order (e.g. disconnected from
  // the rest of the graph) is treated as "not yet reached" rather than "already visited" —
  // there's no step at which it would have been highlighted.
  const isReplaying = replayNodes.length > 0
  const replayPos = replayNodes.indexOf(id)
  const isReplayCurrent = isReplaying && replayPos === replayIndex
  const isReplayUpcoming = isReplaying && (replayPos === -1 || replayPos > replayIndex)

  const ringClass = isReplayCurrent
    ? 'outline outline-2 outline-[var(--accent)]'
    : selected
      ? 'outline outline-2 outline-[var(--accent)] ring-2 ring-[var(--accent)]/30'
      : status === 'error'
        ? 'outline outline-2 outline-[var(--error)]'
        : status === 'success'
          ? 'outline outline-1 outline-[var(--success)]'
          : status === 'skipped'
            ? 'opacity-60'
            : ''

  return (
    <div
      className={`min-w-[190px] overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] ${ringClass} shadow-[var(--shadow-1)] transition-opacity duration-300 ${isReplayUpcoming ? 'opacity-40' : 'opacity-100'}`}
      style={{ borderLeft: `3px solid ${color}` }}
    >
      {inputPorts === 2 ? (
        <>
          <Handle type="target" position={Position.Left} id="left" style={{ top: '35%', background: color, width: 8, height: 8 }} />
          <span className="absolute left-1 text-[9px] text-[var(--text-muted)]" style={{ top: 'calc(35% - 14px)' }}>L</span>
          <Handle type="target" position={Position.Left} id="right" style={{ top: '65%', background: color, width: 8, height: 8 }} />
          <span className="absolute left-1 text-[9px] text-[var(--text-muted)]" style={{ top: 'calc(65% - 14px)' }}>R</span>
        </>
      ) : inputPorts >= 1 ? (
        <Handle type="target" position={Position.Left} style={{ background: color, width: 8, height: 8 }} />
      ) : null}

      <div>
        <div className="flex items-center justify-between gap-2 border-b border-[var(--border-light)] bg-[var(--panel-alt)] px-3 py-1">
          <span className="ui-panel-title">{category}</span>
          {status === 'error' && <span className="text-[var(--error)] text-xs" title={result.error_message}>⚠</span>}
          {status === 'success' && <span className="text-[var(--success)] text-xs">✓</span>}
          {status === 'skipped' && <span className="text-[var(--text-muted)] text-xs" title={result.error_message}>–</span>}
          {isExecuting && !result && <span className="text-[var(--text-muted)] text-xs animate-pulse">…</span>}
        </div>
        <div className="px-3 pb-2 pt-1.5 text-[13px] font-semibold text-[var(--text)]">{data.displayName}</div>
        {result?.success && result.total_row_count != null && (
          <div className="px-3 pb-2 text-xs text-[var(--text-muted)]">{result.total_row_count.toLocaleString()} rows</div>
        )}
        {result && !result.success && (
          <div className="px-3 pb-2 line-clamp-2 text-xs text-[var(--error)]">{result.error_message}</div>
        )}
      </div>

      <Handle type="source" position={Position.Right} style={{ background: color, width: 8, height: 8 }} />
    </div>
  )
}
