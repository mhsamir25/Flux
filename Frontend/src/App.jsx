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

  // The middle column's height is the ceiling for the preview panel, so the resize handle
  // needs a live measurement of it rather than a hardcoded viewport number.
  const middleColumnRef = useRef(null)

  // Whether the configuration panel is showing. ConfigPanel deliberately renders nothing when
  // it isn't (it has no tab of its own any more), so App owns the reopen tab that sits beside
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

  // Restore auth from localStorage — re-fetches the real user via GET /api/users/me rather
  // than trusting a possibly-expired token blindly (see hooks/useAuth.js).
  useEffect(() => {
    restore()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Save button: guests get the auth modal first (with the save request remembered), logged-
  // in users save immediately. Either way, the pipeline saved is whatever is on canvas *at
  // the moment the save actually runs* — for the guest path that's after auth completes, not
  // before, so nothing built while signing in is lost.
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

  // Auto-save to localStorage every 30 seconds. Also carries currentTemplateId along (a real
  // gap before this checkpoint: reloading mid-edit of a saved template lost the link back to
  // it, so the next Save would silently create a duplicate instead of updating in place). For
  // a logged-in user editing an already-saved template, also push the change to the server in
  // the background so a crash/close doesn't lose work the localStorage blob would otherwise
  // strand on this device only.
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

  // Restore autosave or onboarding on first load. The onboarding pipeline only ever
  // auto-loads once per browser — flux_has_visited is written the moment it loads, not when
  // the banner is dismissed, so Dismiss is a session-only UI toggle with nothing left to
  // persist.
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
        // Write an autosave snapshot immediately, not just on the next 30s interval tick —
        // otherwise a reload in the first 30 seconds finds no autosave AND flux_has_visited
        // already set, so the onboarding pipeline (still on canvas) silently vanishes.
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

          {/* Right-hand column: configuration on top, canvas overview beneath it. Both live
              here so neither overlaps the canvas — the minimap used to be a floating overlay
              that permanently covered the bottom-right corner of the graph. */}
          <div className="flex shrink-0">
            <div className="flex w-60 flex-col border-l border-[var(--border)] bg-[var(--panel)]">
              <ConfigPanel />
              {/* Sits below the configuration panel and is a fixed 160px tall rather than
                  filling the column: a minimap stretched down a tall narrow strip scales its
                  nodes to fit the width and ends up showing one huge block instead of the
                  graph. The config panel above it (flex-1) absorbs whatever height is left. */}
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
