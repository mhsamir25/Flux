import { useEffect, useRef, useState } from 'react'

import executionApi from '../../api/executionApi'
import usePipelineStore from '../../store/pipelineStore'

const SOURCE_FILE_SPEC = {
  read_csv: { ext: 'csv', accept: '.csv,text/csv', label: 'Read CSV' },
  read_xlsx: {
    ext: 'xlsx',
    accept: '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    label: 'Read XLSX',
  },
}

const CATEGORY_COLOR = {
  SOURCE: 'var(--cat-source)',
  TRANSFORM: 'var(--cat-transform)',
  AGGREGATE: 'var(--cat-aggregate)',
  JOIN: 'var(--cat-join)',
  OUTPUT: 'var(--cat-output)',
}

const CATEGORY_ORDER = ['SOURCE', 'TRANSFORM', 'AGGREGATE', 'JOIN', 'OUTPUT']
const CATEGORY_LABEL = {
  SOURCE: 'Source',
  TRANSFORM: 'Transform',
  AGGREGATE: 'Aggregate',
  JOIN: 'Join',
  OUTPUT: 'Output',
}

// Which sections are folded, persisted per browser. A palette of 18 nodes across 5 sections
// is mostly whitespace once you're working — the section you need is usually one of them —
// and re-folding the same four sections on every reload is exactly the friction collapsing
// them is meant to remove. Read defensively: a corrupt/hand-edited value just means "all
// sections open" rather than a blank sidebar.
const SECTIONS_KEY = 'flux_sidebar_sections'

function readCollapsedSections() {
  try {
    const raw = localStorage.getItem(SECTIONS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(parsed) ? parsed : [])
  } catch {
    return new Set()
  }
}

// Renders the palette by grouping GET /api/nodes' response by category (PLAN.md §13) — never
// a hardcoded node list. Dragging an item onto the canvas creates a node via
// ReactFlowCanvas.jsx's onDrop, which reads these exact dataTransfer keys.
//
// Two levels of collapse: the whole sidebar folds to a narrow rail of category dots (so the
// canvas gets the width back while the palette is still one click away), and each category
// section folds independently.
export default function NodeSidebar() {
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const collapsed = usePipelineStore((s) => s.sidebarCollapsed)
  const toggleSidebar = usePipelineStore((s) => s.toggleSidebar)
  const nodes = usePipelineStore((s) => s.nodes)
  const selectedNodeId = usePipelineStore((s) => s.selectedNodeId)
  const addNode = usePipelineStore((s) => s.addNode)
  const updateNodeConfig = usePipelineStore((s) => s.updateNodeConfig)

  const [collapsedSections, setCollapsedSections] = useState(readCollapsedSections)
  const [uploadStatus, setUploadStatus] = useState(null) // { kind: 'loading' | 'success' | 'error', message }
  const fileInputRefs = useRef({})

  const handleSourceFile = async (nodeId, file) => {
    const spec = SOURCE_FILE_SPEC[nodeId]
    if (!spec || !file) return

    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext !== spec.ext) {
      setUploadStatus({
        kind: 'error',
        message: `Only .${spec.ext} files are allowed for ${spec.label}.`,
      })
      return
    }

    setUploadStatus({ kind: 'loading', message: `Uploading ${file.name}…` })
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await executionApi.post('/api/data/upload', formData)
      const { data_reference_id, row_count } = res.data

      const selectedSameType = nodes.find(
        (n) => n.id === selectedNodeId && n.data.nodeType === nodeId
      )
      const unconfiguredExisting = nodes.find(
        (n) => n.data.nodeType === nodeId && !n.data.config?.data_reference_id
      )
      const existingTarget = selectedSameType || unconfiguredExisting
      const existingSourceCount = nodes.filter(
        (n) => n.data.nodeType === 'read_csv' || n.data.nodeType === 'read_xlsx'
      ).length

      const targetNodeId =
        existingTarget?.id ??
        addNode(nodeId, spec.label, { x: 80, y: 150 + existingSourceCount * 110 })

      updateNodeConfig(targetNodeId, { data_reference_id })
      setUploadStatus({
        kind: 'success',
        message: `${file.name} — ${row_count.toLocaleString()} rows`,
      })
    } catch (err) {
      setUploadStatus({
        kind: 'error',
        message: err.response?.data?.detail || 'Upload failed.',
      })
    }
  }

  useEffect(() => {
    try {
      localStorage.setItem(SECTIONS_KEY, JSON.stringify([...collapsedSections]))
    } catch {
      // Private-browsing / quota — folding just won't persist. Not worth surfacing.
    }
  }, [collapsedSections])

  const toggleSection = (category) =>
    setCollapsedSections((previous) => {
      const next = new Set(previous)
      next.has(category) ? next.delete(category) : next.add(category)
      return next
    })

  // A rail dot means "I want this category", so it expands the sidebar *and* unfolds that
  // section — otherwise every dot would land you on the same generic palette.
  const revealSection = (category) => {
    setCollapsedSections((previous) => {
      if (!previous.has(category)) return previous
      const next = new Set(previous)
      next.delete(category)
      return next
    })
    if (collapsed) toggleSidebar()
  }

  const grouped = CATEGORY_ORDER
    .map((category) => ({
      category,
      nodes: nodeCatalogue.filter((n) => n.category === category),
    }))
    .filter((group) => group.nodes.length > 0)

  const onDragStart = (e, node) => {
    e.dataTransfer.setData('application/flux-node-type', node.id)
    e.dataTransfer.setData('application/flux-node-name', node.display_name)
    e.dataTransfer.effectAllowed = 'move'
  }

  // Collapsed rail: just the category dots, each expanding the sidebar onto that section.
  if (collapsed) {
    return (
      <aside className="flex w-9 shrink-0 flex-col items-center gap-1 overflow-y-auto border-r border-[var(--border)] bg-[var(--panel)] py-2">
        <button
          type="button"
          onClick={toggleSidebar}
          title="Show node palette"
          aria-label="Show node palette"
          className="ui-btn ui-btn-ghost mb-1 px-1.5 py-1"
        >
          »
        </button>
        {grouped.map(({ category, nodes }) => (
          <button
            key={category}
            type="button"
            onClick={() => revealSection(category)}
            title={`${CATEGORY_LABEL[category]} (${nodes.length})`}
            aria-label={CATEGORY_LABEL[category]}
            className="flex h-7 w-7 items-center justify-center rounded-[var(--radius)] transition-transform hover:scale-110"
            style={{ background: `color-mix(in srgb, ${CATEGORY_COLOR[category]} 22%, transparent)` }}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_COLOR[category] }} />
          </button>
        ))}
      </aside>
    )
  }

  return (
    <aside className="flex w-56 shrink-0 flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--panel)]">
      <div className="flex shrink-0 items-center justify-between px-3 pb-1 pt-3">
        <h2 className="ui-panel-title">Nodes</h2>
        <button
          type="button"
          onClick={toggleSidebar}
          title="Collapse palette"
          aria-label="Collapse palette"
          className="ui-btn ui-btn-ghost px-1.5 py-0.5"
        >
          «
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {nodeCatalogue.length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">Loading node types…</p>
        )}

        {grouped.map(({ category, nodes }) => {
          const isFolded = collapsedSections.has(category)
          return (
            <div key={category} className="mb-1">
              <button
                type="button"
                onClick={() => toggleSection(category)}
                aria-expanded={!isFolded}
                className="mb-1 flex w-full items-center gap-1.5 rounded-[var(--radius)] px-1 py-1 text-left transition-colors hover:bg-[var(--panel-hover)]"
              >
                {/* Chevron rotates rather than swapping glyphs, so the fold direction reads
                    the same in every section. */}
                <span
                  className="text-[9px] text-[var(--text-muted)] transition-transform duration-150"
                  style={{ transform: isFolded ? 'rotate(0deg)' : 'rotate(90deg)' }}
                >
                  ▶
                </span>
                <span className="flex flex-1 items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--text)]">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: CATEGORY_COLOR[category] }}
                  />
                  {CATEGORY_LABEL[category]}
                </span>
                <span className="text-[10px] tabular-nums text-[var(--text-muted)]">
                  {nodes.length}
                </span>
              </button>

              {!isFolded && (
                <div className="flex flex-col gap-1">
                  {nodes.map((node) => {
                    const sourceSpec = SOURCE_FILE_SPEC[node.id]
                    if (sourceSpec) {
                      const isUploading = uploadStatus?.kind === 'loading'
                      return (
                        <div key={node.id}>
                          <input
                            ref={(el) => {
                              fileInputRefs.current[node.id] = el
                            }}
                            type="file"
                            accept={sourceSpec.accept}
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0]
                              e.target.value = ''
                              if (file) handleSourceFile(node.id, file)
                            }}
                          />
                          <button
                            type="button"
                            disabled={isUploading}
                            onClick={() => fileInputRefs.current[node.id]?.click()}
                            title={`Import a .${sourceSpec.ext} file from your computer`}
                            className="flex w-full cursor-pointer select-none items-center justify-between rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] px-2.5 py-1.5 text-left text-[13px] text-[var(--text)] transition-colors hover:bg-[var(--panel-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                            style={{ borderLeft: `3px solid ${CATEGORY_COLOR[category]}` }}
                          >
                            <span>{node.display_name}</span>
                            <span className="text-[10px] text-[var(--text-muted)]">.{sourceSpec.ext}</span>
                          </button>
                        </div>
                      )
                    }

                    return (
                      <div
                        key={node.id}
                        draggable
                        onDragStart={(e) => onDragStart(e, node)}
                        title={node.formula_exportable ? undefined : 'No Excel formula equivalent'}
                        className="cursor-grab select-none rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] px-2.5 py-1.5 text-[13px] text-[var(--text)] transition-colors hover:bg-[var(--panel-hover)] active:cursor-grabbing"
                        style={{ borderLeft: `3px solid ${CATEGORY_COLOR[category]}` }}
                      >
                        {node.display_name}
                      </div>
                    )
                  })}
                  {category === 'SOURCE' && uploadStatus && (
                    <p
                      className={`mt-0.5 px-1 text-[11px] ${
                        uploadStatus.kind === 'error'
                          ? 'text-[var(--error)]'
                          : uploadStatus.kind === 'success'
                            ? 'text-[var(--success)]'
                            : 'text-[var(--text-muted)]'
                      }`}
                    >
                      {uploadStatus.message}
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </aside>
  )
}
