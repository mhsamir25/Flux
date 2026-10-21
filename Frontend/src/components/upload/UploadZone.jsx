import { useRef, useState } from 'react'

import executionApi from '../../api/executionApi'
import usePipelineStore from '../../store/pipelineStore'

const ACCEPTED_EXTENSIONS = ['csv', 'xlsx']


export default function UploadZone() {
  const [isDragging, setIsDragging] = useState(false)
  const [status, setStatus] = useState(null) // { kind: 'loading' | 'success' | 'error', message }
  const inputRef = useRef(null)

  const nodes = usePipelineStore((s) => s.nodes)
  const addNode = usePipelineStore((s) => s.addNode)
  const updateNodeConfig = usePipelineStore((s) => s.updateNodeConfig)

  const handleFile = async (file) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setStatus({ kind: 'error', message: 'Only .csv and .xlsx files are supported.' })
      return
    }

    setStatus({ kind: 'loading', message: `Uploading ${file.name}…` })
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await executionApi.post('/api/data/upload', formData)
      const { data_reference_id, row_count } = res.data

      const nodeType = ext === 'csv' ? 'read_csv' : 'read_xlsx'
      const existing = nodes.find((n) => n.data.nodeType === nodeType)
      const sourceNodeId =
        existing?.id ?? addNode(nodeType, ext === 'csv' ? 'Read CSV' : 'Read XLSX', { x: 80, y: 150 })

      updateNodeConfig(sourceNodeId, { data_reference_id })
      setStatus({ kind: 'success', message: `${file.name} — ${row_count.toLocaleString()} rows` })
    } catch (err) {
      setStatus({ kind: 'error', message: err.response?.data?.detail || 'Upload failed.' })
    }
  }

  const statusColor =
    status?.kind === 'error' ? 'text-[var(--error)]' : status?.kind === 'success' ? 'text-[var(--success)]' : 'text-[var(--text-muted)]'

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
      }}
      onClick={() => inputRef.current?.click()}
      className={`m-2 shrink-0 cursor-pointer rounded-[var(--radius)] border border-dashed px-3 py-2 text-xs transition-colors ${
        isDragging
          ? 'border-[var(--accent)] bg-[var(--accent-bg)]'
          : 'border-[var(--border)] bg-[var(--panel-alt)] hover:bg-[var(--panel-hover)]'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
          e.target.value = '' // allow re-selecting the same file name after a failed/repeat upload
        }}
      />
      <span className={statusColor}>
        {status ? status.message : 'Drop a CSV or XLSX file here, or click to browse'}
      </span>
    </div>
  )
}
