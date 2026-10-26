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


const FALLBACK_SIZE = { width: 200, height: 150 }

export default function CanvasMiniMap() {
  const nodeCatalogue = usePipelineStore((s) => s.nodeCatalogue)
  const boxRef = useRef(null)
  const [size, setSize] = useState(FALLBACK_SIZE)


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
