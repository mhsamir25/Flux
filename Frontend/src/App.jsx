import { useEffect, useRef, useState } from 'react'
import { ReactFlowProvider } from '@xyflow/react'

import TopBar            from './components/topbar/TopBar.jsx'
import NodeSidebar        from './components/sidebar/NodeSidebar.jsx'
import ReactFlowCanvas    from './components/canvas/ReactFlowCanvas.jsx'
import CanvasMiniMap      from './components/canvas/CanvasMiniMap.jsx'
import ConfigPanel        from './components/config/ConfigPanel.jsx'
import DataPreviewTable   from './components/preview/DataPreviewTable.jsx'
import PreviewResizeHandle from './components/preview/PreviewResizeHandle.jsx'
import FormulaPanel       from './components/formula/FormulaPanel.jsx'
import TemplateBrowser    from './components/templates/TemplateBrowser.jsx'
import SaveModal          from './components/templates/SaveModal.jsx'
import AuthModal          from './components/auth/AuthModal.jsx'
import OnboardingBanner   from './components/onboarding/OnboardingBanner.jsx'

import usePipelineStore from './store/pipelineStore'
import executionApi     from './api/executionApi'
import useAuth          from './hooks/useAuth'
import { buildOnboardingPipeline } from './onboardingPipeline'

export default function App() {
  const setNodeCatalogue = usePipelineStore(s => s.setNodeCatalogue)
  const showAuth          = usePipelineStore(s => s.showAuthModal)
  const setShowAuth       = usePipelineStore(s => s.setShowAuthModal)
  const pendingAction     = usePipelineStore(s => s.pendingAction)
  const setPendingAction  = usePipelineStore(s => s.setPendingAction)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [saveNotification, setSaveNotification] = useState(null)
  const [showOnboarding, setShowOnboarding] = useState(false)

  // The middle column's height is the ceiling for the preview panel, so the resize handle
  // needs a live measurement of it rather than a hardcoded viewport number.
  const middleColumnRef = useRef(null)

  // Whether the configuration panel is showing. ConfigPanel deliberately renders nothing when
  // it isn't (it has no tab of its own any more), so App owns the reopen tab that sits beside
  // the canvas overview.
  const selectedNodeId        = usePipelineStore(s => s.selectedNodeId)
  const selectedNodeIds       = usePipelineStore(s => s.selectedNodeIds)
  const configPanelCollapsed  = usePipelineStore(s => s.configPanelCollapsed)
  const toggleConfigPanel     = usePipelineStore(s => s.toggleConfigPanel)
  const isConfigPanelOpen     = (!!selectedNodeId || (selectedNodeIds && selectedNodeIds.length > 1)) && !configPanelCollapsed

  const { isGuest, restore } = useAuth()

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

  // Save button: guests get the auth modal first (with the save request remembered); logged-
  // in users open the Save modal immediately to choose whether to create a new template or
  // update the active one.
  const handleSaveClick = () => {
    const { nodes } = usePipelineStore.getState()
    if (!nodes?.length) {
      window.alert('Your canvas is empty. Add nodes to build a pipeline before saving.')
      return
    }
    if (isGuest) {
      setPendingAction('save')
      setShowAuth(true)
      return
    }
    setShowSaveModal(true)
  }

  const handleAuthSuccess = () => {
    if (pendingAction === 'save') {
      setPendingAction(null)
      setShowSaveModal(true)
    }
  }

  const handleSaveSuccess = (msg) => {
    setSaveNotification(msg)
    setTimeout(() => setSaveNotification(null), 3500)
  }

  // Auto-save to localStorage every 30 seconds for instant reload across tab close / crash.
  // Note: we do not automatically overwrite database templates in the background, which would
  // silently mutate and overwrite templates without user knowledge or consent.
  useEffect(() => {
    const id = setInterval(() => {
      const { nodes, edges, csvData, currentTemplateId, currentTemplateName } = usePipelineStore.getState()
      try {
        localStorage.setItem(
          'flux_autosave',
          JSON.stringify({ nodes, edges, csvData, currentTemplateId, currentTemplateName, savedAt: Date.now() })
        )
      } catch {
        // Ignore localStorage quota or availability errors
      }
    }, 30000)
    return () => clearInterval(id)
  }, [])

  const dismissOnboarding = () => setShowOnboarding(false)

  // Restore autosave or onboarding on first load. The onboarding pipeline only ever
  // auto-loads once per browser — flux_has_visited is written the moment it loads, not when
  // the banner is dismissed, so Dismiss is a session-only UI toggle with nothing left to
  // persist.
  useEffect(() => {
    try {
      const saved = localStorage.getItem('flux_autosave')
      if (saved) {
        const { nodes, edges, csvData, currentTemplateId, currentTemplateName } = JSON.parse(saved)
        if (nodes?.length) {
          usePipelineStore.getState().loadPipeline(nodes, edges)
          if (csvData) usePipelineStore.getState().setCsvData(csvData, 'autosave.csv')
          if (currentTemplateId) {
            usePipelineStore.getState().setCurrentTemplate(currentTemplateId, currentTemplateName || null)
          }
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
            JSON.stringify({ nodes, edges, csvData, currentTemplateId: null, currentTemplateName: null, savedAt: Date.now() })
          )
        } catch {
          // Ignore localStorage errors
        }
        setShowOnboarding(true)
      }
    } catch {
      // Ignore localStorage parse errors
    }
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
        {showSaveModal && (
          <SaveModal
            onClose={() => setShowSaveModal(false)}
            onSaveSuccess={handleSaveSuccess}
          />
        )}
        {showAuth && (
          <AuthModal
            onClose={() => { setShowAuth(false); setPendingAction(null) }}
            onSuccess={handleAuthSuccess}
          />
        )}
        {saveNotification && (
          <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--panel)] px-3 py-2 text-xs font-medium shadow-md text-[var(--success)]">
            <span>✓</span>
            <span>{saveNotification}</span>
          </div>
        )}
      </div>
    </ReactFlowProvider>
  )
}
