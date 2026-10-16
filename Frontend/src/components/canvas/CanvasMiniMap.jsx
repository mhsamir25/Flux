import { useCallback, useEffect, useRef } from 'react'
import {
  ReactFlow, Background, Controls,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import usePipelineStore from '../../store/pipelineStore'
import FluxNode from '../nodes/FluxNode'
import executionApi from '../../api/executionApi'
import { getTargetPort } from '../../utils/edgePorts'
import ReplayControls from '../replay/ReplayControls'

const nodeTypes = { fluxNode: FluxNode }

const debounce = (fn, ms) => {
  let t
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms) }
}

export default function ReactFlowCanvas() {
  const nodes          = usePipelineStore(s => s.nodes)
  const edges          = usePipelineStore(s => s.edges)
  const onNodesChange  = usePipelineStore(s => s.onNodesChange)
  const onEdgesChange  = usePipelineStore(s => s.onEdgesChange)
  const onConnect      = usePipelineStore(s => s.onConnect)
  const setSelectedNode= usePipelineStore(s => s.setSelectedNode)
  const csvData        = usePipelineStore(s => s.csvData)
  const setNodeResults = usePipelineStore(s => s.setNodeResults)
  const setFormulaResult = usePipelineStore(s => s.setFormulaResult)
  const setExecuting   = usePipelineStore(s => s.setExecuting)
  const executionError = usePipelineStore(s => s.executionError)
  const setExecutionError = usePipelineStore(s => s.setExecutionError)
  const addNode        = usePipelineStore(s => s.addNode)

  // Debounced execute
  const executeRef = useRef(null)
  const formulaRef = useRef(null)

  const runExecution = useCallback(async (nodeList, edgeList, csv) => {
    if (!nodeList.length) return
    setExecuting(true)
    try {
      const payload = {
        nodes: nodeList.map(n => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edgeList.map(e => ({ source_node_id: e.source, target_node_id: e.target, target_port: getTargetPort(e) })),
        csv_data: csv || undefined,
      }
      const res = await executionApi.post('/api/pipeline/execute', payload)
      setNodeResults(res.data.node_results)
      setExecutionError(null)
    } catch (err) {
      console.error('Execution error:', err)
      setExecutionError(
        err.response?.status === 429
          ? "You're editing faster than the server can keep up — results will resume in a moment."
          : 'Could not refresh results — the last successful run is still shown.'
      )
    } finally {
      setExecuting(false)
    }
  }, [setNodeResults, setExecuting, setExecutionError])

  const runFormula = useCallback(async (nodeList, edgeList) => {
    if (!nodeList.length) return
    try {
      const payload = {
        nodes: nodeList.map(n => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edgeList.map(e => ({ source_node_id: e.source, target_node_id: e.target, target_port: getTargetPort(e) })),
      }
      const res = await executionApi.post('/api/formula/generate', payload)
      setFormulaResult(res.data)
    } catch (err) {
      console.error('Formula error:', err)
    }
  }, [setFormulaResult])

  useEffect(() => {
    executeRef.current = debounce(runExecution, 300)
    formulaRef.current = debounce(runFormula, 500)
  }, [runExecution, runFormula])

  useEffect(() => {
    executeRef.current?.(nodes, edges, csvData)
    formulaRef.current?.(nodes, edges)
  }, [nodes, edges, csvData])

  // Handle drag over / drop from sidebar
  const onDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    const type = e.dataTransfer.getData('application/flux-node-type')
    const displayName = e.dataTransfer.getData('application/flux-node-name')
    if (!type) return
    const bounds = e.currentTarget.getBoundingClientRect()
    const position = { x: e.clientX - bounds.left - 80, y: e.clientY - bounds.top - 30 }
    addNode(type, displayName, position)
  }, [addNode])

  const handleConnect = useCallback(async (params) => {
    // Validate edge via FastAPI before connecting (POST /api/pipeline/validate-edge needs the
    // whole current graph, not just the two endpoint nodes, since it checks for cycles).
    try {
      const res = await executionApi.post('/api/pipeline/validate-edge', {
        nodes: nodes.map(n => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edges.map(e => ({ source_node_id: e.source, target_node_id: e.target, target_port: getTargetPort(e) })),
        proposed_edge: {
          source_node_id: params.source,
          target_node_id: params.target,
          target_port: params.targetHandle === 'left' || params.targetHandle === 'right' ? params.targetHandle : null,
        },
      })
      if (!res.data.valid) {
        alert(`Cannot connect: ${res.data.error_message}`)
        return
      }
    } catch (err) {
      // Server unreachable: don't block the user from building offline-ish, but make the
      // silent-allow visible in the console rather than swallowing it entirely.
      console.warn('Edge validation request failed; connecting without server-side validation.', err)
    }
    onConnect(params)
  }, [nodes, edges, onConnect])

  const showHint = nodes.length === 0

  return (
    <div className="relative flex-1 h-full" onDragOver={onDragOver} onDrop={onDrop}>
      {showHint && (
        <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 text-[var(--text-muted)]">
          <div className="text-sm">Drag nodes from the sidebar to start building your pipeline</div>
        </div>
      )}
      {executionError && (
        <div className="absolute top-3 left-1/2 z-20 -translate-x-1/2 rounded-[var(--radius)] border border-[var(--error)] bg-[var(--panel)] px-3 py-1.5 text-xs text-[var(--error)] shadow-[var(--shadow-2)]">
          {executionError}
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onNodeClick={(_, node) => setSelectedNode(node.id)}
        onPaneClick={() => setSelectedNode(null)}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[16, 16]}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ style: { stroke: 'var(--border)', strokeWidth: 1.5 } }}
      >
        <Background variant={BackgroundVariant.Lines} gap={20} color="var(--border-light)" />
        <Controls />
      </ReactFlow>
      <ReplayControls />
    </div>
  )
}
