import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 180_000, // 3 min — pipeline runs take time
  headers: { 'Content-Type': 'application/json' },
})

// ── Response interceptor — normalize errors ──────────────
http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const message =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      'Unknown error'
    return Promise.reject(new Error(message))
  }
)

// ── API methods ───────────────────────────────────────────

/**
 * POST /run-query
 * Runs question through all 3 pipelines + all eval runners
 */
export const runQuery = (payload) =>
  http.post('/run-query', payload)

/**
 * GET /runs
 * Filterable list of pipeline runs
 */
export const getRuns = (filters = {}) => {
  const params = {}
  if (filters.pipeline_name)   params.pipeline_name   = filters.pipeline_name
  if (filters.category)        params.category        = filters.category
  if (filters.max_faithfulness) params.max_faithfulness = filters.max_faithfulness
  if (filters.min_faithfulness) params.min_faithfulness = filters.min_faithfulness
  params.limit = filters.limit || 50
  return http.get('/runs', { params })
}

/**
 * GET /runs/:id
 * Full detail: run + metrics + claims + trace
 */
export const getRunDetail = (runId) =>
  http.get(`/runs/${runId}`)

/**
 * GET /metrics/summary
 * Aggregated averages per strategy — powers heatmap
 */
export const getMetricsSummary = (category = '') => {
  const params = {}
  if (category) params.category = category
  return http.get('/metrics/summary', { params })
}

/**
 * GET /benchmark/status
 * Progress for the file-backed benchmark runner
 */
export const getBenchmarkStatus = () =>
  http.get('/benchmark/status')

/**
 * GET /benchmark/summary
 * File-backed benchmark aggregates
 */
export const getBenchmarkSummary = () =>
  http.get('/benchmark/summary')

/**
 * GET /benchmark/results
 * File-backed benchmark question results
 */
export const getBenchmarkResults = (filters = {}) => {
  const params = {}
  if (filters.category) params.category = filters.category
  if (filters.source) params.source = filters.source
  if (filters.search) params.search = filters.search
  if (filters.limit) params.limit = filters.limit
  return http.get('/benchmark/results', { params })
}
