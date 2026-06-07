import { useCallback, useEffect, useRef } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import usePipelineStore from '../../store/pipelineStore'
import FluxNode from '../nodes/FluxNode'
import executionApi from '../../api/executionApi'

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
  const addNode        = usePipelineStore(s => s.addNode)
  const nodeCatalogue  = usePipelineStore(s => s.nodeCatalogue)

  // Debounced execute
  const executeRef = useRef(null)
  const formulaRef = useRef(null)

  const runExecution = useCallback(async (nodeList, edgeList, csv) => {
    if (!nodeList.length) return
    setExecuting(true)
    try {
      const payload = {
        nodes: nodeList.map(n => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edgeList.map(e => ({ source_node_id: e.source, target_node_id: e.target, target_port: e.targetHandle === 'right' ? 'right' : null })),
        csv_data: csv || '',
      }
      const res = await executionApi.post('/api/execute', payload)
      setNodeResults(res.data.node_results)
    } catch (err) {
      console.error('Execution error:', err)
    } finally {
      setExecuting(false)
    }
  }, [setNodeResults, setExecuting])

  const runFormula = useCallback(async (nodeList, edgeList) => {
    if (!nodeList.length) return
    try {
      const payload = {
        nodes: nodeList.map(n => ({ id: n.id, type: n.data.nodeType, config: n.data.config || {} })),
        edges: edgeList.map(e => ({ source_node_id: e.source, target_node_id: e.target })),
      }
      const res = await executionApi.post('/api/formula', payload)
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
    // Validate edge via FastAPI before connecting
    try {
      const sourceNode = nodes.find(n => n.id === params.source)
      const targetNode = nodes.find(n => n.id === params.target)
      if (sourceNode && targetNode) {
        const res = await executionApi.post('/api/validate-edge', {
          source_node_id: params.source,
          source_node_type: sourceNode.data.nodeType,
          source_config: sourceNode.data.config || {},
          target_node_id: params.target,
          target_node_type: targetNode.data.nodeType,
          target_config: targetNode.data.config || {},
        })
        if (!res.data.valid) {
          alert(`Cannot connect: ${res.data.message}`)
          return
        }
      }
    } catch {}
    onConnect(params)
  }, [nodes, onConnect])

  const showHint = nodes.length === 0

  return (
    <div className="canvas-wrapper" onDragOver={onDragOver} onDrop={onDrop}>
      {showHint && (
        <div className="canvas-hint">
          <div className="canvas-hint-icon">⬡</div>
          <div className="canvas-hint-text">Drag nodes from the sidebar to start building your pipeline</div>
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
        defaultEdgeOptions={{ animated: true, style: { stroke: 'var(--border-light)', strokeWidth: 2 } }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="var(--border)" />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const cat = nodeCatalogue.find(c => c.id === n.data?.nodeType)?.category || 'TRANSFORM'
            return ({ SOURCE: '#818cf8', TRANSFORM: '#34d399', AGGREGATE: '#fb923c', JOIN: '#a78bfa', OUTPUT: '#60a5fa' })[cat] || '#666'
          }}
          maskColor="rgba(13,15,20,0.7)"
        />
      </ReactFlow>
    </div>
  )
}
