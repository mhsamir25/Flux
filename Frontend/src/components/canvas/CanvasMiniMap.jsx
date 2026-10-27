import { useEffect, useRef, useState } from 'react'
import { MiniMap } from '@xyflow/react'

import usePipelineStore from '../../store/pipelineStore'

const CATEGORY_COLOR = {
  SOURCE: 'var(--cat-source)',
  TRANSFORM: 'var(--cat-transform)',
  AGGREGATE: 'var(--cat-aggregate)',
  JOIN: 'var(--cat-join)',
  OUTPUT: 'var(--cat-output)',
}

// The canvas overview, rendered in the right-hand column under the configuration panel
// instead of floating over the canvas.
//
// It was an overlay before, which meant it permanently covered whatever was parked in the
// bottom-right corner of the graph — nodes get dragged there constantly, so it was sitting on
// top of real work. React Flow's MiniMap works anywhere inside ReactFlowProvider (it reads
// the same internal store the canvas writes to), so nothing about it needed to be inside the
// <ReactFlow> element. See the .flux-minimap rule in index.css for the positioning reset.

// MiniMap's own source computes its viewBox like this:
//
//   const elementWidth  = style?.width  ?? 200
//   const scaledWidth   = boundingRect.width / elementWidth
//   const viewScale     = Math.max(scaledWidth, scaledHeight)
//   const x             = boundingRect.x - (viewScale * elementWidth - boundingRect.width) / 2 - offset
//
// So style.width/style.height must be NUMBERS. Passing '100%' makes that division NaN and the
// whole viewBox — and therefore every node in the overview — collapses to nothing. That means
// the size has to be measured, not expressed as a percentage.
const FALLBACK_SIZE = { width: 200, height: 150 }

export default function CanvasMiniMap() {
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const boxRef = useRef(null)
  const [size, setSize] = useState(FALLBACK_SIZE)

  // Measure the box we're given and hand MiniMap the resulting pixel numbers. A
  // ResizeObserver rather than a one-shot read, so the overview stays correct when the
  // column is resized or the root font size differs from the 16px default (every width in
  // this app is rem-based, so that is not a hypothetical).
  useEffect(() => {
    const element = boxRef.current
    if (!element) return undefined

    const measure = () => {
      const { clientWidth: width, clientHeight: height } = element
      if (width > 0 && height > 0) setSize({ width, height })
    }
    measure()

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure)
      return () => window.removeEventListener('resize', measure)
    }
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={boxRef} className="h-full w-full">
      <MiniMap
        pannable
        zoomable
        ariaLabel="Canvas overview"
        // Numbers, not '100%' — see the note above.
        style={{ width: size.width, height: size.height, background: 'var(--panel)' }}
        maskColor="rgba(128, 128, 128, 0.18)"
        nodeStrokeWidth={1}
        nodeBorderRadius={3}
        nodeColor={(node) => {
          const category = nodeCatalogue.find((c) => c.id === node.data?.nodeType)?.category || 'TRANSFORM'
          return CATEGORY_COLOR[category] || 'var(--text-muted)'
        }}
      />
    </div>
  )
}
