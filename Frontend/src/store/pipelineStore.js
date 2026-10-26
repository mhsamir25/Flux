import { create } from 'zustand'
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'

const usePipelineStore = create((set, get) => ({
  // React Flow state
  nodes: [],
  edges: [],
  onNodesChange: (changes) => set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (connection) => set({ edges: addEdge({ ...connection, animated: true }, get().edges) }),

  // Execution results keyed by node id
  nodeResults: {},
  setNodeResults: (results) => set({ nodeResults: results }),

  // Selected node id for config panel
  selectedNodeId: null,
  setSelectedNode: (id) => set({ selectedNodeId: id }),

  // CSV data (never sent to Django; only for execution)
  csvData: null,
  csvFileName: null,
  setCsvData: (data, name) => set({ csvData: data, csvFileName: name }),

  // Node catalogue from FastAPI
  nodeCatalogue: [],
  setNodeCatalogue: (catalogue) => set({ nodeCatalogue: catalogue }),

  // Excel formula result
  formulaResult: null,
  setFormulaResult: (result) => set({ formulaResult: result }),

  accessToken: null,
  username: null,
  setAuth: (token, username) => {
    try { localStorage.setItem('flux_access_token', token) } catch {}
    set({ accessToken: token, username })
  },
  clearAuth: () => {
    try { localStorage.removeItem('flux_access_token') } catch {}
    set({ accessToken: null, username: null })
  },

  showAuthModal: false,
  setShowAuthModal: (v) => set({ showAuthModal: v }),


  pendingAction: null,
  setPendingAction: (v) => set({ pendingAction: v }),

  currentTemplateId: null,
  setCurrentTemplateId: (id) => set({ currentTemplateId: id }),

  // Preview panel: which node to show preview for
  previewNodeId: null,
  setPreviewNode: (id) => set({ previewNodeId: id }),

 
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  
  configPanelCollapsed: false,
  toggleConfigPanel: () => set((s) => ({ configPanelCollapsed: !s.configPanelCollapsed })),


  previewHeight: 192,
  setPreviewHeight: (height) => set({ previewHeight: height }),

  // Execution running state
  isExecuting: false,
  setExecuting: (v) => set({ isExecuting: v }),

  
  executionError: null,
  setExecutionError: (v) => set({ executionError: v }),

  // Replay Mode State
  replayNodes: [], // Topologically sorted node IDs
  replayIndex: -1, // Current step in replay
  
  startReplay: () => {
    const { nodes, edges } = get()
    // Simple topological sort
    const inDegree = {}; const adj = {};
    nodes.forEach(n => { inDegree[n.id] = 0; adj[n.id] = [] })
    edges.forEach(e => {
      if (adj[e.source] && inDegree[e.target] !== undefined) {
        adj[e.source].push(e.target)
        inDegree[e.target]++
      }
    })
    const q = nodes.filter(n => inDegree[n.id] === 0).map(n => n.id)
    const sorted = []
    while (q.length > 0) {
      const curr = q.shift()
      sorted.push(curr)
      adj[curr].forEach(child => {
        inDegree[child]--
        if (inDegree[child] === 0) q.push(child)
      })
    }
    set({ replayNodes: sorted, replayIndex: 0, previewNodeId: sorted[0] || null, selectedNodeId: sorted[0] || null })
  },
  
  nextReplayStep: () => {
    const { replayNodes, replayIndex } = get()
    if (replayIndex < replayNodes.length - 1) {
      const nextIdx = replayIndex + 1
      set({ replayIndex: nextIdx, previewNodeId: replayNodes[nextIdx], selectedNodeId: replayNodes[nextIdx] })
    }
  },
  
  prevReplayStep: () => {
    const { replayNodes, replayIndex } = get()
    if (replayIndex > 0) {
      const prevIdx = replayIndex - 1
      set({ replayIndex: prevIdx, previewNodeId: replayNodes[prevIdx], selectedNodeId: replayNodes[prevIdx] })
    }
  },
  
  stopReplay: () => set({ replayNodes: [], replayIndex: -1 }),

  // Update a single node's config
  updateNodeConfig: (nodeId, newConfig) => set({
    nodes: get().nodes.map(n =>
      n.id === nodeId ? { ...n, data: { ...n.data, config: { ...n.data.config, ...newConfig } } } : n
    )
  }),


  addNode: (type, displayName, position) => {
    const newNode = {
      id: crypto.randomUUID(),
      type: 'fluxNode',
      position,
      data: { nodeType: type, displayName, config: {} },
    }
    set({ nodes: [...get().nodes, newNode] })
    return newNode.id
  },

  
  resetCanvas: () => set({
    nodes: [], edges: [], nodeResults: {}, selectedNodeId: null, previewNodeId: null,
    formulaResult: null, currentTemplateId: null, csvData: null, csvFileName: null,
  }),

  // Load pipeline from template
  loadPipeline: (nodes, edges) => set({ nodes, edges, nodeResults: {}, selectedNodeId: null }),
}))

export default usePipelineStore
