import { create } from 'zustand'
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'

const usePipelineStore = create((set, get) => ({
  // React Flow state
  nodes: [],
  edges: [],
  onNodesChange: (changes) => {
    const currentNodes = get().nodes
    const nextNodes = applyNodeChanges(changes, currentNodes)

    // Handle any node removals (e.g. from ReactFlow deleteKeyCode) to safely clean
    // up connected edges, nodeResults, and selection references.
    const removedChanges = changes.filter(c => c.type === 'remove')
    if (removedChanges.length > 0) {
      const removedSet = new Set(removedChanges.map(c => c.id))
      const currentEdges = get().edges
      const nextEdges = currentEdges.filter(e => !removedSet.has(e.source) && !removedSet.has(e.target))

      const updatedResults = { ...get().nodeResults }
      removedChanges.forEach(c => { delete updatedResults[c.id] })

      const { selectedNodeId, selectedNodeIds, previewNodeId } = get()
      set({
        nodes: nextNodes,
        edges: nextEdges,
        nodeResults: updatedResults,
        selectedNodeId: removedSet.has(selectedNodeId) ? null : selectedNodeId,
        selectedNodeIds: (selectedNodeIds || []).filter(id => !removedSet.has(id)),
        previewNodeId: removedSet.has(previewNodeId) ? null : previewNodeId,
      })
      return
    }

    set({ nodes: nextNodes })
  },
  onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (connection) => set({ edges: addEdge({ ...connection, animated: true }, get().edges) }),

  // Mouse mode for canvas interactions: 'select' (box selection on drag) vs 'pan' (pan on drag)
  mouseMode: 'select',
  setMouseMode: (mode) => set({ mouseMode: mode }),

  // Execution results keyed by node id
  nodeResults: {},
  setNodeResults: (results) => set({ nodeResults: results }),

  // Selected node ids
  selectedNodeId: null,
  selectedNodeIds: [],
  setSelectedNode: (id) => set({
    selectedNodeId: id,
    selectedNodeIds: id ? [id] : [],
  }),
  setSelectedNodes: (ids) => set({
    selectedNodeIds: ids,
    selectedNodeId: ids.length === 1 ? ids[0] : null,
  }),
  clearSelection: () => set((s) => ({
    nodes: s.nodes.map(n => n.selected ? { ...n, selected: false } : n),
    selectedNodeId: null,
    selectedNodeIds: [],
  })),

  // Delete all currently selected nodes (or a specified subset)
  deleteSelectedNodes: () => {
    const { nodes, edges, nodeResults, selectedNodeId, selectedNodeIds, previewNodeId } = get()
    const toDeleteIds = new Set([
      ...(selectedNodeIds || []),
      ...nodes.filter(n => n.selected).map(n => n.id),
      ...(selectedNodeId ? [selectedNodeId] : []),
    ])
    if (toDeleteIds.size === 0) return

    const remainingNodes = nodes.filter(n => !toDeleteIds.has(n.id))
    const remainingEdges = edges.filter(e => !toDeleteIds.has(e.source) && !toDeleteIds.has(e.target))
    const updatedResults = { ...nodeResults }
    toDeleteIds.forEach(id => { delete updatedResults[id] })

    set({
      nodes: remainingNodes,
      edges: remainingEdges,
      nodeResults: updatedResults,
      selectedNodeId: null,
      selectedNodeIds: [],
      previewNodeId: toDeleteIds.has(previewNodeId) ? null : previewNodeId,
    })
  },

  deleteNode: (nodeId) => {
    const { nodes, edges, nodeResults, selectedNodeId, selectedNodeIds, previewNodeId } = get()
    const remainingNodes = nodes.filter(n => n.id !== nodeId)
    const remainingEdges = edges.filter(e => e.source !== nodeId && e.target !== nodeId)
    const updatedResults = { ...nodeResults }
    delete updatedResults[nodeId]

    set({
      nodes: remainingNodes,
      edges: remainingEdges,
      nodeResults: updatedResults,
      selectedNodeId: selectedNodeId === nodeId ? null : selectedNodeId,
      selectedNodeIds: (selectedNodeIds || []).filter(id => id !== nodeId),
      previewNodeId: previewNodeId === nodeId ? null : previewNodeId,
    })
  },

  deleteEdge: (edgeId) => {
    set({
      edges: get().edges.filter((e) => e.id !== edgeId),
    })
  },

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

  // Auth state. Persistence to localStorage lives here (not scattered across components) so
  // every caller of setAuth/clearAuth — login, register, session restore on mount — gets it
  // for free. `username` is populated from GET /api/users/me's real `email` field, never
  // decoded out of the JWT: the backend's token payload is only {sub, aud, exp} (verified in
  // Phase 8), no email in it at all.
  accessToken: null,
  username: null,
  setAuth: (token, username) => {
    try { localStorage.setItem('flux_access_token', token) } catch { /* ignore storage error */ }
    set({ accessToken: token, username })
  },
  clearAuth: () => {
    try { localStorage.removeItem('flux_access_token') } catch { /* ignore storage error */ }
    set({ accessToken: null, username: null })
  },

  // Login/register modal visibility — triggered explicitly (Save button while a guest) or
  // by the API client on a 401 from a protected route (PLAN.md §13).
  showAuthModal: false,
  setShowAuthModal: (v) => set({ showAuthModal: v }),

  // Set when the Save button opens the auth modal for a guest — checked by the modal's
  // onSuccess handler to immediately complete the save the user was trying to do, using
  // whatever pipeline was on canvas *before* authenticating (PLAN.md §12's guest->account
  // upgrade path), rather than making them rebuild after signing in.
  pendingAction: null,
  setPendingAction: (v) => set({ pendingAction: v }),

  // The template this canvas was last loaded from or saved to, if any — a brand-new unsaved
  // pipeline stays null until the user explicitly saves it once (§12).
  currentTemplateId: null,
  currentTemplateName: null,
  setCurrentTemplate: (id, name) => set({ currentTemplateId: id, currentTemplateName: name }),
  setCurrentTemplateId: (id) => set({ currentTemplateId: id }),

  // Preview panel: which node to show preview for
  previewNodeId: null,
  setPreviewNode: (id) => set({ previewNodeId: id }),

  // --- Panel visibility -----------------------------------------------------------
  // The canvas is the thing you actually work in, and the two side panels were eating 512px
  // of it (224px palette + 288px config) whether or not they had anything to show. Both are
  // collapsible now, and both prefs live here rather than in component state so they survive
  // re-renders of the panels themselves and can be persisted in one place. Neither is reset
  // by resetCanvas: how you've arranged your workspace isn't part of the pipeline.
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  // The config panel only earns its width when a node is selected — it has nothing to
  // configure otherwise — so it hides itself when nothing is selected, and a manual collapse
  // additionally keeps it out of the way for the node you *are* editing.
  configPanelCollapsed: false,
  toggleConfigPanel: () => set((s) => ({ configPanelCollapsed: !s.configPanelCollapsed })),

  // Preview panel height in px, driven by the drag handle between the canvas and the panel
  // (see PreviewResizeHandle.jsx). Kept in the store rather than in DataPreviewTable so the
  // handle and the panel can't disagree about the height, and so the value survives a
  // re-render. Read back from localStorage by that component, not here, to keep this file
  // free of storage side effects.
  previewHeight: 192,
  setPreviewHeight: (height) => set({ previewHeight: height }),

  // Execution running state
  isExecuting: false,
  setExecuting: (v) => set({ isExecuting: v }),

  // Set when the most recent execute call failed outright (network error, rate limit, server
  // error) — as opposed to a node-level error, which comes back as a normal 200 with that
  // node's own result marked unsuccessful. Without this, a failed request left nodeResults
  // frozen on whatever the last successful response happened to be, with nothing telling the
  // user their latest edit never actually took effect on the canvas.
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

  // Add a node from the sidebar drag. Returns the new node's id so callers that need to act
  // on it immediately (e.g. UploadZone setting data_reference_id right after auto-creating a
  // source node) don't have to re-query/guess which node in the array is the one just added.
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

  // Reset canvas — also clears currentTemplateId/csvData, since a brand-new blank canvas
  // isn't tied to any saved template and shouldn't carry over the previous pipeline's data
  // (both were missing before Phase 11 checkpoint 5: "New" left stale template linkage and
  // CSV data in place, which would have made the very next Save silently overwrite the
  // template you just walked away from instead of prompting for a new one).
  resetCanvas: () => set({
    nodes: [], edges: [], nodeResults: {}, selectedNodeId: null, selectedNodeIds: [], previewNodeId: null,
    formulaResult: null, currentTemplateId: null, currentTemplateName: null, csvData: null, csvFileName: null,
  }),

  // Load pipeline from template
  pipelineLoadCount: 0,
  loadPipeline: (nodes, edges) => set((s) => ({
    nodes,
    edges,
    nodeResults: {},
    selectedNodeId: null,
    selectedNodeIds: [],
    pipelineLoadCount: s.pipelineLoadCount + 1,
  })),
}))

export default usePipelineStore
