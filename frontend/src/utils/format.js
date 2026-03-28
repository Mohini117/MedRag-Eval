/** Format a 0-1 float as a percentage string: 0.863 → "86%" */
export const fmtPct = (v, decimals = 0) =>
  v == null ? '—' : `${(v * 100).toFixed(decimals)}%`

/** Format milliseconds: 1234.5 → "1234ms" */
export const fmtMs = (v) =>
  v == null ? '—' : `${Math.round(v)}ms`

/** Truncate a string with ellipsis */
export const truncate = (str, n = 80) =>
  str && str.length > n ? `${str.slice(0, n)}…` : str || ''

/** Map failure_source to human label */
export const failureLabel = (src) => ({
  none:      'No Failure',
  retrieval: 'Retrieval',
  llm:       'LLM',
}[src] || src || '—')

/** Map claim status to display label */
export const claimLabel = (s) => ({
  supported:    'Supported',
  hallucinated: 'Hallucinated',
  partial:      'Partial',
}[s] || s || '—')

/** Pipeline name → short label */
export const stratLabel = (name) => ({
  strategy_a_fixed_chunking:        'Strategy A · Fixed',
  strategy_b_semantic_chunking:     'Strategy B · Semantic',
  strategy_c_parent_child_chunking: 'Strategy C · Parent-Child',
}[name] || name || '—')

/** Get strategy accent CSS variable */
export const stratAccentVar = (name) => ({
  strategy_a_fixed_chunking:        'var(--strat-a)',
  strategy_b_semantic_chunking:     'var(--strat-b)',
  strategy_c_parent_child_chunking: 'var(--strat-c)',
}[name] || 'var(--text-2)')

/** Score → semantic color CSS var */
export const scoreColor = (v) => {
  if (v == null) return 'var(--text-2)'
  const pct = v * 100
  if (pct >= 80) return 'var(--green)'
  if (pct >= 50) return 'var(--amber)'
  return 'var(--red)'
}

export const scoreDimBg = (v) => {
  if (v == null) return 'var(--bg-3)'
  const pct = v * 100
  if (pct >= 80) return 'var(--green-dim)'
  if (pct >= 50) return 'var(--amber-dim)'
  return 'var(--red-dim)'
}

/** Format ISO timestamp */
export const fmtTime = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}