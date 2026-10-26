import { useState } from 'react'

import executionApi from '../../api/executionApi'
import usePipelineStore from '../../store/pipelineStore'


function parsedPipelineToFlow(parsed, nodeCatalogue) {
  const spacing = 220
  const nodes = parsed.nodes.map((n, i) => {
    const catalogueEntry = nodeCatalogue.find((c) => c.id === n.type)
    return {
      id: n.id,
      type: 'fluxNode',
      position: { x: 80 + i * spacing, y: 150 },
      data: { nodeType: n.type, displayName: catalogueEntry?.display_name || n.type, config: n.config || {} },
    }
  })
  const edges = parsed.edges.map((e, i) => ({
    id: `parsed-e${i}`,
    source: e.source_node_id,
    target: e.target_node_id,
    ...(e.target_port ? { targetHandle: e.target_port } : {}),
    animated: true,
    style: { stroke: 'var(--border)', strokeWidth: 1.5 },
  }))
  return { nodes, edges }
}

export default function FormulaPanel() {
  const formulaResult = usePipelineStore((s) => s.formulaResult)
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const nodes = usePipelineStore((s) => s.nodes)
  const loadPipeline = usePipelineStore((s) => s.loadPipeline)

  const [showExplain, setShowExplain] = useState(false)
  const [showPasteIn, setShowPasteIn] = useState(false)
  const [pasteValue, setPasteValue] = useState('')
  const [parseError, setParseError] = useState(null)
  const [copied, setCopied] = useState(false)

  const hasFormula = Boolean(formulaResult?.formula)

  const handleCopy = async () => {
    if (!formulaResult?.formula) return
  
    try {
      await navigator.clipboard.writeText(formulaResult.formula)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.warn('Could not copy to clipboard:', err)
    }
  }

  const handleParse = async () => {
    setParseError(null)
    if (!pasteValue.trim()) return
    try {
      const res = await executionApi.post('/api/formula/parse', { formula: pasteValue })
      if (res.data.nodes) {
        if (nodes.length > 0 && !window.confirm('Replace the current canvas with the parsed pipeline?')) {
          return
        }
        const { nodes: flowNodes, edges: flowEdges } = parsedPipelineToFlow(res.data, nodeCatalogue)
        loadPipeline(flowNodes, flowEdges)
        setShowPasteIn(false)
        setPasteValue('')
      } else {
        setParseError(res.data)
      }
    } catch {
      setParseError({ message: 'Request failed — is the backend running?', supported_patterns: [] })
    }
  }

  return (
    <div className="flex shrink-0 flex-col border-t border-[var(--border)] bg-[var(--panel)]">
      <div className="flex h-9 items-center gap-2 bg-[var(--panel-alt)] px-3">
        <span className="ui-panel-title shrink-0">Formula</span>
        <code className={`flex-1 truncate text-xs ${hasFormula ? 'text-[var(--text)]' : 'text-[var(--text-muted)]'}`}>
          {formulaResult?.formula || 'No formula available for this pipeline'}
        </code>
        {formulaResult?.compatibility && (
          <span className="shrink-0 text-[10px] text-[var(--text-muted)]">{formulaResult.compatibility}</span>
        )}
        <button
          type="button"
          disabled={!hasFormula}
          onClick={handleCopy}
          className="ui-btn ui-btn-default shrink-0"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
        <button
          type="button"
          onClick={() => setShowExplain((v) => !v)}
          className="ui-btn ui-btn-default shrink-0"
        >
          {showExplain ? 'Hide Explain' : 'Explain'}
        </button>
        <button
          type="button"
          onClick={() => setShowPasteIn((v) => !v)}
          className="ui-btn ui-btn-default shrink-0"
        >
          Paste Formula
        </button>
      </div>

      {showExplain && (
        <div className="whitespace-pre-line border-t border-[var(--border-light)] px-4 py-2 text-xs text-[var(--text-muted)]">
          {formulaResult?.explanation || 'Nothing to explain yet.'}
        </div>
      )}

      {showPasteIn && (
        <div className="border-t border-[var(--border-light)] px-4 py-2">
          <p className="mb-1 text-[10px] text-[var(--text-muted)]">
            Supported: FILTER, SORT, UNIQUE, XLOOKUP, VLOOKUP, SUMIF(S), AVERAGEIF(S), COUNTIF(S)
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={pasteValue}
              onChange={(e) => setPasteValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleParse()}
              placeholder="=FILTER(Sheet1!A1:Z1000, [age]>30)"
              className="ui-input flex-1 font-mono"
            />
            <button
              type="button"
              onClick={handleParse}
              className="ui-btn ui-btn-primary shrink-0"
            >
              Parse
            </button>
          </div>
          {parseError && (
            <p className="mt-1 text-[10px] text-[var(--error)]">
              {parseError.message}
              {parseError.supported_patterns?.length > 0 && ` (Supported: ${parseError.supported_patterns.join(', ')})`}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
