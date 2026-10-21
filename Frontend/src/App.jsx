import { useEffect, useRef, useState } from 'react'
import { ReactFlowProvider } from '@xyflow/react'

import TopBar            from './components/topbar/TopBar.jsx'
import NodeSidebar        from './components/sidebar/NodeSidebar.jsx'
import UploadZone         from './components/upload/UploadZone.jsx'
import ReactFlowCanvas    from './components/canvas/ReactFlowCanvas.jsx'
import CanvasMiniMap      from './components/canvas/CanvasMiniMap.jsx'
import ConfigPanel        from './components/config/ConfigPanel.jsx'
import DataPreviewTable   from './components/preview/DataPreviewTable.jsx'
import PreviewResizeHandle from './components/preview/PreviewResizeHandle.jsx'
import FormulaPanel       from './components/formula/FormulaPanel.jsx'
import TemplateBrowser    from './components/templates/TemplateBrowser.jsx'
import AuthModal          from './components/auth/AuthModal.jsx'
import OnboardingBanner   from './components/onboarding/OnboardingBanner.jsx'

import usePipelineStore from './store/pipelineStore'
import executionApi     from './api/executionApi'
import useAuth          from './hooks/useAuth'
import useTemplates     from './hooks/useTemplates'
import { buildOnboardingPipeline } from './onboardingPipeline'

export default function App() {
  const setNodeCatalogue = usePipelineStore(s => s.setNodeCatalogue)
  const showAuth          = usePipelineStore(s => s.showAuthModal)
  const setShowAuth       = usePipelineStore(s => s.setShowAuthModal)
  const pendingAction     = usePipelineStore(s => s.pendingAction)
  const setPendingAction  = usePipelineStore(s => s.setPendingAction)
  const currentTemplateId = usePipelineStore(s => s.currentTemplateId)
  const setCurrentTemplateId = usePipelineStore(s => s.setCurrentTemplateId)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showOnboarding, setShowOnboarding] = useState(false)

 
  // needs a live measurement of it rather than a hardcoded viewport number.
  const middleColumnRef = useRef(null)

  // the canvas overview.
  const selectedNodeId        = usePipelineStore(s => s.selectedNodeId)
  const configPanelCollapsed  = usePipelineStore(s => s.configPanelCollapsed)
  const toggleConfigPanel     = usePipelineStore(s => s.toggleConfigPanel)
  const isConfigPanelOpen     = !!selectedNodeId && !configPanelCollapsed

  const { isGuest, restore } = useAuth()
  const { create: createTemplate, update: updateTemplate } = useTemplates()

  // Fetch node catalogue on mount
  useEffect(() => {
    executionApi.get('/api/nodes')
      .then(res => setNodeCatalogue(res.data))
      .catch(() => console.warn('Could not reach the Flux backend — is it running?'))
  }, [])

 .
  useEffect(() => {
    restore()
    
  }, [])

 
  const performSave = async () => {
    const { nodes, edges } = usePipelineStore.getState()
    const pipelineJson = { version: '1.0', nodes, edges }
    try {
      if (currentTemplateId) {
        await updateTemplate(currentTemplateId, { pipeline_json: pipelineJson })
      } else {
        const name = window.prompt('Name this pipeline:', 'My Pipeline')
        if (!name) return
        const created = await createTemplate(name, null, pipelineJson)
        setCurrentTemplateId(created.id)
      }
    } catch (err) {
      window.alert(`Could not save: ${err.response?.data?.detail || 'unknown error'}`)
    }
  }

  const handleSaveClick = () => {
    if (isGuest) {
      setPendingAction('save')
      setShowAuth(true)
      return
    }
    performSave()
  }

  const handleAuthSuccess = () => {
    if (pendingAction === 'save') {
      setPendingAction(null)
      performSave()
    }
  }


  useEffect(() => {
    const id = setInterval(async () => {
      const { nodes, edges, csvData, currentTemplateId, accessToken } = usePipelineStore.getState()
      try {
        localStorage.setItem(
          'flux_autosave',
          JSON.stringify({ nodes, edges, csvData, currentTemplateId, savedAt: Date.now() })
        )
      } catch {}

      if (accessToken && currentTemplateId) {
        try {
          await updateTemplate(currentTemplateId, { pipeline_json: { version: '1.0', nodes, edges } })
        } catch (err) {
          console.warn('Background template sync failed:', err)
        }
      }
    }, 30000)
    return () => clearInterval(id)
  }, [updateTemplate])

  const dismissOnboarding = () => setShowOnboarding(false)

  
  useEffect(() => {
    try {
      const saved = localStorage.getItem('flux_autosave')
      if (saved) {
        const { nodes, edges, csvData, currentTemplateId } = JSON.parse(saved)
        if (nodes?.length) {
          usePipelineStore.getState().loadPipeline(nodes, edges)
          if (csvData) usePipelineStore.getState().setCsvData(csvData, 'autosave.csv')
          if (currentTemplateId) setCurrentTemplateId(currentTemplateId)
          return
        }
      }

      const hasVisited = localStorage.getItem('flux_has_visited')
      if (!hasVisited) {
        const { nodes, edges, csvData } = buildOnboardingPipeline()
        usePipelineStore.getState().loadPipeline(nodes, edges)
        usePipelineStore.getState().setCsvData(csvData, 'student_grades.csv')
        localStorage.setItem('flux_has_visited', 'true')
        
        try {
          localStorage.setItem(
            'flux_autosave',
            JSON.stringify({ nodes, edges, csvData, currentTemplateId: null, savedAt: Date.now() })
          )
        } catch {}
        setShowOnboarding(true)
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <ReactFlowProvider>
      <div className="flex h-screen flex-col bg-[var(--bg)] text-[var(--text)]">
        <TopBar
          onShowTemplates={() => setShowTemplates(true)}
          onShowAuth={() => setShowAuth(true)}
          onSave={handleSaveClick}
        />

        <div className="relative flex flex-1 overflow-hidden">
          <NodeSidebar />

          <div ref={middleColumnRef} className="relative flex flex-1 flex-col overflow-hidden">
            {showOnboarding && <OnboardingBanner onDismiss={dismissOnboarding} />}
            <UploadZone />
            <ReactFlowCanvas />
            <PreviewResizeHandle containerRef={middleColumnRef} />
            <DataPreviewTable />
          </div>

          {}
          <div className="flex shrink-0">
            <div className="flex w-60 flex-col border-l border-[var(--border)] bg-[var(--panel)]">
              <ConfigPanel />
              {}
              <div className="flux-minimap h-40 shrink-0 border-t border-[var(--border)] bg-[var(--panel-alt)] p-2">
                <CanvasMiniMap />
              </div>
            </div>

            {!isConfigPanelOpen && (
              <button
                type="button"
                onClick={toggleConfigPanel}
                title="Show configuration"
                aria-label="Show configuration"
                className="ui-btn ui-btn-ghost w-7 shrink-0 items-start justify-start rounded-none border-y-0 border-r-0 pt-3"
              >
                ‹
              </button>
            )}
          </div>
        </div>

        <FormulaPanel />

        {showTemplates && (
          <TemplateBrowser onClose={() => setShowTemplates(false)} onRequestAuth={() => setShowAuth(true)} />
        )}
        {showAuth && (
          <AuthModal
            onClose={() => { setShowAuth(false); setPendingAction(null) }}
            onSuccess={handleAuthSuccess}
          />
        )}
      </div>
    </ReactFlowProvider>
  )
}
