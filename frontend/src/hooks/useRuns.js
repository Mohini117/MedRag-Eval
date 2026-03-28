import { useState, useEffect, useCallback } from 'react'
import { getRuns, getRunDetail } from '../api/client'

export function useRuns(initialFilters = {}) {
  const [runs, setRuns]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [filters, setFilters] = useState(initialFilters)

  const fetch = useCallback(async (overrides = {}) => {
    setLoading(true)
    setError(null)
    try {
      const result = await getRuns({ ...filters, ...overrides })
      setRuns(result.runs || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { fetch() }, [filters])

  return { runs, loading, error, filters, setFilters, refetch: fetch }
}

export function useRunDetail(runId) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!runId) { setData(null); return }
    setLoading(true)
    setError(null)
    getRunDetail(runId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [runId])

  return { data, loading, error }
}