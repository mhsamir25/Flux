import { useCallback, useState } from 'react'

import executionApi from '../api/executionApi'

// Auth-aware only in the sense that every call here 401s for a guest (current_active_user on
// the backend, §16) — the interceptor already surfaces the auth modal on that; the guest-
// prompt UI itself lives in TemplateBrowser, which checks useAuth().isGuest before ever
// calling list().
export default function useTemplates() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const list = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await executionApi.get('/api/templates')
      setTemplates(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load templates.')
    } finally {
      setLoading(false)
    }
  }, [])

  const create = useCallback(async (name, description, pipelineJson) => {
    const res = await executionApi.post('/api/templates', {
      name,
      description: description || null,
      pipeline_json: pipelineJson,
    })
    setTemplates((prev) => [...prev, res.data])
    return res.data
  }, [])

  const update = useCallback(async (id, payload) => {
    const res = await executionApi.put(`/api/templates/${id}`, payload)
    setTemplates((prev) => prev.map((t) => (t.id === id ? res.data : t)))
    return res.data
  }, [])

  const remove = useCallback(async (id) => {
    await executionApi.delete(`/api/templates/${id}`)
    setTemplates((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return { templates, loading, error, list, create, update, remove }
}
