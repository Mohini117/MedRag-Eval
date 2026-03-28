import { useState, useRef, useCallback } from 'react'
import { runQuery } from '../api/client'

export function useRunQuery() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef(null)

  const execute = useCallback(async (payload) => {
    setLoading(true)
    setError(null)
    setData(null)
    setElapsed(0)

    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000)

    try {
      const result = await runQuery(payload)
      setData(result)
      return result
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setLoading(false)
      clearInterval(timerRef.current)
    }
  }, [])

  return { data, loading, error, elapsed, execute }
}