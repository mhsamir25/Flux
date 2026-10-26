import axios from 'axios'

import usePipelineStore from '../store/pipelineStore'


const executionApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})


executionApi.interceptors.request.use((config) => {
  const token = usePipelineStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})


executionApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      usePipelineStore.getState().setShowAuthModal(true)
    }
    return Promise.reject(error)
  }
)

export default executionApi
