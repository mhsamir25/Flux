import { useEffect, useState } from 'react'
import { ReactFlowProvider } from '@xyflow/react'

import TopBar           from './components/topbar/TopBar.jsx'
import NodeSidebar      from './components/sidebar/NodeSidebar.jsx'
import ReactFlowCanvas  from './components/canvas/ReactFlowCanvas.jsx'
import ConfigPanel      from './components/config/ConfigPanel.jsx'
import DataPreviewTable from './components/preview/DataPreviewTable.jsx'
import FormulaPanel     from './components/formula/FormulaPanel.jsx'
import TemplateBrowser  from './components/templates/TemplateBrowser.jsx'
import AuthModal        from './components/auth/AuthModal.jsx'

import usePipelineStore from './store/pipelineStore'
import executionApi     from './api/executionApi'

export default function App() {
  const setNodeCatalogue = usePipelineStore(s => s.setNodeCatalogue)
  const setAuth          = usePipelineStore(s => s.setAuth)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showAuth,      setShowAuth]      = useState(false)

  // Fetch node catalogue on mount
  useEffect(() => {
    executionApi.get('/api/nodes')
      .then(res => setNodeCatalogue(res.data))
      .catch(() => console.warn('Could not reach execution backend at http://localhost:8001'))
  }, [])

  // Restore auth from localStorage
  useEffect(() => {
    const token = localStorage.getItem('flux_access_token')
    if (token) {
      // Decode username from JWT payload (no lib needed)
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        setAuth(token, payload.username || payload.user_id || 'User')
      } catch {}
    }
  }, [])

  // Auto-save to localStorage every 30 seconds
  useEffect(() => {
    const id = setInterval(() => {
      const { nodes, edges, csvData } = usePipelineStore.getState()
      try {
        localStorage.setItem('flux_autosave', JSON.stringify({ nodes, edges, csvData, savedAt: Date.now() }))
      } catch {}
    }, 30000)
    return () => clearInterval(id)
  }, [])

  // Restore autosave or onboarding on first load
  useEffect(() => {
    try {
      const saved = localStorage.getItem('flux_autosave')
      if (saved) {
        const { nodes, edges, csvData } = JSON.parse(saved)
        if (nodes?.length) {
          usePipelineStore.getState().loadPipeline(nodes, edges)
          if (csvData) usePipelineStore.getState().setCsvData(csvData, 'autosave.csv')
          return
        }
      }

      const onboarded = localStorage.getItem('flux_onboarded')
      if (!onboarded) {
        const csv = 'Name,Subject,Grade\nAlice,Math,85\nBob,Math,42\nCharlie,Science,90\nDiana,Science,35\nEve,History,75'
        const nodes = [
          { id: 'n1', type: 'fluxNode', position: { x: 50, y: 100 }, data: { nodeType: 'read_csv', displayName: 'Read CSV', config: {} } },
          { id: 'n2', type: 'fluxNode', position: { x: 300, y: 100 }, data: { nodeType: 'filter', displayName: 'Filter Passing', config: { column: 'Grade', operator: '≥', value: '50' } } },
          { id: 'n3', type: 'fluxNode', position: { x: 550, y: 100 }, data: { nodeType: 'add_calculated_column', displayName: 'Add Status', config: { new_column_name: 'Status', left_operand: 'Pass', operator: '+', right_operand: '' } } },
          { id: 'n4', type: 'fluxNode', position: { x: 850, y: 100 }, data: { nodeType: 'data_table', displayName: 'Data Table', config: {} } },
        ]
        const edges = [
          { id: 'e1', source: 'n1', target: 'n2', targetHandle: 'default', sourceHandle: 'out', animated: true, style: { stroke: 'var(--border-light)', strokeWidth: 2 } },
          { id: 'e2', source: 'n2', target: 'n3', targetHandle: 'default', sourceHandle: 'out', animated: true, style: { stroke: 'var(--border-light)', strokeWidth: 2 } },
          { id: 'e3', source: 'n3', target: 'n4', targetHandle: 'default', sourceHandle: 'out', animated: true, style: { stroke: 'var(--border-light)', strokeWidth: 2 } },
        ]
        usePipelineStore.getState().loadPipeline(nodes, edges)
        usePipelineStore.getState().setCsvData(csv, 'student_grades.csv')
        localStorage.setItem('flux_onboarded', 'true')
      }
    } catch {}
  }, [])

  return (
    <ReactFlowProvider>
      <div className="app-shell">
        <TopBar
          onShowTemplates={() => setShowTemplates(true)}
          onShowAuth={() => setShowAuth(true)}
        />

        <div className="app-body" style={{ position: 'relative' }}>
          <NodeSidebar />

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
            <ReactFlowCanvas />
            <DataPreviewTable />
          </div>

          <ConfigPanel />
        </div>

        <FormulaPanel />

        {showTemplates && <TemplateBrowser onClose={() => setShowTemplates(false)} />}
        {showAuth      && <AuthModal      onClose={() => setShowAuth(false)} />}
      </div>
    </ReactFlowProvider>
  )
}
