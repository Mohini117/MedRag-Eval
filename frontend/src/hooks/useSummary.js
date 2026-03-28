import { useState, useEffect, useCallback } from 'react'
import { getMetricsSummary } from '../api/client'

export function useSummary(initialCategory = '') {
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [category, setCategory] = useState(initialCategory)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getMetricsSummary(category)
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [category])

  useEffect(() => { fetch() }, [category])

  return { data, loading, error, category, setCategory, refetch: fetch }
}