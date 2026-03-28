import { useState } from 'react'
import { useRuns, useRunDetail } from '../hooks/useRuns'
import Badge from '../components/ui/Badge'
import Shimmer from '../components/ui/Shimmer'
import PageHeader from '../components/layout/PageHeader'
import { fmtPct, fmtMs, truncate, scoreColor } from '../utils/format'

const CATEGORIES = ['diabetes', 'hypertension', 'asthma', 'depression', 'cancer']

const METRICS = [
  { key: 'faithfulness',      label: 'Faithfulness'  },
  { key: 'answer_relevancy',  label: 'Relevancy'     },
  { key: 'context_precision', label: 'Precision'     },
  { key: 'context_recall',    label: 'Recall'        },
]

function StatCard({ label, count, color, desc }) {
  return (
    <div style={{
      background: 'var(--bg-1)', border: '1px solid var(--border)',
      borderTop: `2px solid ${color}`,
      borderRadius: 'var(--radius-lg)', padding: '16px 20px',
    }}>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 8 }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: 34, fontWeight: 600, color, lineHeight: 1, marginBottom: 4 }}>
        {count}
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>{desc}</div>
    </div>
  )
}

function ClaimDetail({ claim, index }) {
  const color = claim.status === 'hallucinated'
    ? 'var(--red)'
    : claim.status === 'supported'
    ? 'var(--green)'
    : 'var(--amber)'

  const dimBg = claim.status === 'hallucinated'
    ? 'var(--red-dim)'
    : claim.status === 'supported'
    ? 'var(--green-dim)'
    : 'var(--amber-dim)'

  return (
    <div style={{
      padding: '12px 14px',
      background: dimBg,
      borderRadius: 'var(--radius-md)',
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Badge type={claim.status} />
        <span className="mono" style={{ fontSize: 9, color: 'var(--text-2)' }}>#{index}</span>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-0)', lineHeight: 1.6, margin: 0 }}>
        {claim.claim_text}
      </p>
      {claim.supporting_context && (
        <div style={{
          marginTop: 10, padding: '8px 10px',
          background: 'rgba(0,0,0,0.25)', borderRadius: 6,
        }}>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 4 }}>
            SOURCE CONTEXT
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-2)', lineHeight: 1.55, margin: 0 }}>
            {truncate(claim.supporting_context, 200)}
          </p>
        </div>
      )}
    </div>
  )
}

function RunDetailPanel({ runId, onClose }) {
  const { data, loading } = useRunDetail(runId)

  return (
    <div
      className="anim-slide-in"
      style={{
        background: 'var(--bg-1)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
      }}
    >
      {/* Panel header */}
      <div style={{
        padding: '12px 16px',
        background: 'var(--bg-2)', borderBottom: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0,
      }}>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.08em' }}>
          CLAIM BREAKDOWN
        </span>
        <button
          onClick={onClose}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-2)', fontSize: 18, lineHeight: 1,
            padding: '2px 6px', borderRadius: 4,
            transition: 'color var(--dur)',
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-0)'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-2)'}
        >
          ×
        </button>
      </div>

      <div style={{ overflowY: 'auto', flex: 1 }}>
        {loading ? (
          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1, 2, 3, 4].map((i) => <Shimmer key={i} height={70} />)}
          </div>
        ) : data ? (
          <div style={{ padding: '16px' }}>
            {/* Question */}
            <div style={{ marginBottom: 14 }}>
              <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 6 }}>QUESTION</div>
              <p style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.65 }}>{data.question}</p>
            </div>

            {/* Answer */}
            <div style={{
              padding: '12px 14px', marginBottom: 14,
              background: 'var(--bg-3)', borderRadius: 'var(--radius-md)',
              borderLeft: '3px solid var(--blue)',
            }}>
              <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 6 }}>ANSWER</div>
              <p style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.65, margin: 0 }}>{data.answer}</p>
            </div>

            {/* Metric mini grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {METRICS.map((m) => {
                const v = data.metrics?.[m.key]
                const color = scoreColor(v)
                return (
                  <div key={m.key} style={{
                    padding: '10px 12px', background: 'var(--bg-3)',
                    borderRadius: 'var(--radius-sm)',
                  }}>
                    <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 4 }}>
                      {m.label.toUpperCase()}
                    </div>
                    <span className="mono" style={{ fontSize: 18, fontWeight: 600, color }}>
                      {fmtPct(v)}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* Claims */}
            {data.claims?.length > 0 && (
              <div>
                <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 10 }}>
                  CLAIMS · {data.claims.length} extracted
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {data.claims.map((c, i) => (
                    <ClaimDetail key={i} claim={c} index={i} />
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default function FailureExplorer() {
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [localFilters, setLocalFilters] = useState({
    pipeline_name: '', category: '', max_faithfulness: '',
  })

  const { runs, loading, error, setFilters } = useRuns({ limit: 50 })

  const applyFilters = () => setFilters({ ...localFilters, limit: 50 })

  const highRisk = runs.filter((r) => r.metrics?.faithfulness != null && r.metrics.faithfulness < 0.5).length
  const caution  = runs.filter((r) => r.metrics?.faithfulness != null && r.metrics.faithfulness >= 0.5 && r.metrics.faithfulness < 0.8).length
  const safe     = runs.filter((r) => r.metrics?.faithfulness != null && r.metrics.faithfulness >= 0.8).length

  const selectStyle = {
    padding: '7px 10px', fontSize: 12,
    background: 'var(--bg-3)', color: 'var(--text-0)',
    border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
    outline: 'none', fontFamily: 'var(--font-ui)', cursor: 'pointer',
  }

  return (
    <div style={{ padding: 'calc(var(--nav-h) + 32px) var(--page-pad) 48px', maxWidth: 1300, margin: '0 auto' }}>
      <PageHeader
        title="Failure Explorer"
        accent="Explorer"
        subtitle="Filter pipeline runs by failure type, strategy, or faithfulness threshold. Click any row to inspect the full claim-level hallucination breakdown."
      />

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 24 }}>
        <StatCard label="HIGH RISK"    count={highRisk} color="var(--red)"   desc="faithfulness < 50%" />
        <StatCard label="CAUTION"      count={caution}  color="var(--amber)" desc="faithfulness 50–80%" />
        <StatCard label="SAFE"         count={safe}     color="var(--green)" desc="faithfulness ≥ 80%" />
      </div>

      {/* Filter bar */}
      <div style={{
        background: 'var(--bg-1)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: '14px 20px',
        marginBottom: 20, display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end',
      }}>
        {[
          {
            key: 'pipeline_name', label: 'STRATEGY',
            options: [
              { value: '', label: 'All strategies' },
              { value: 'strategy_a_fixed_chunking',        label: 'A · Fixed Chunking' },
              { value: 'strategy_b_semantic_chunking',     label: 'B · Semantic Chunking' },
              { value: 'strategy_c_parent_child_chunking', label: 'C · Parent-Child' },
            ],
          },
          {
            key: 'category', label: 'CATEGORY',
            options: [
              { value: '', label: 'All categories' },
              ...CATEGORIES.map((c) => ({ value: c, label: c })),
            ],
          },
        ].map((f) => (
          <div key={f.key}>
            <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 6 }}>
              {f.label}
            </div>
            <select
              value={localFilters[f.key]}
              onChange={(e) => setLocalFilters((p) => ({ ...p, [f.key]: e.target.value }))}
              style={selectStyle}
            >
              {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        ))}

        <div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 6 }}>
            MAX FAITHFULNESS
          </div>
          <input
            type="number" min="0" max="1" step="0.1"
            placeholder="e.g. 0.5"
            value={localFilters.max_faithfulness}
            onChange={(e) => setLocalFilters((p) => ({ ...p, max_faithfulness: e.target.value }))}
            style={{ ...selectStyle, width: 120 }}
          />
        </div>

        <button
          onClick={applyFilters}
          style={{
            padding: '8px 18px',
            background: 'var(--bg-4)', color: 'var(--text-0)',
            border: '1px solid var(--border-hi)',
            borderRadius: 'var(--radius-sm)', fontSize: 12,
            fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em', transition: 'all var(--dur)',
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--green)'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-hi)'}
        >
          APPLY →
        </button>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', marginBottom: 16,
          background: 'var(--red-dim)', border: '1px solid rgba(232,68,90,0.3)',
          borderRadius: 'var(--radius-sm)', color: 'var(--red)', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Table + detail panel */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: selectedRunId ? '1fr 440px' : '1fr',
        gap: 16,
        alignItems: 'start',
      }}>
        {/* Runs table */}
        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          {loading ? (
            <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[1, 2, 3, 4, 5].map((i) => <Shimmer key={i} height={46} />)}
            </div>
          ) : runs.length === 0 ? (
            <div style={{ padding: '4rem', textAlign: 'center' }}>
              <div className="serif" style={{ fontSize: 22, color: 'var(--text-2)', marginBottom: 8 }}>No runs found</div>
              <p className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                Run a query first or adjust your filters
              </p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-2)', borderBottom: '1px solid var(--border)' }}>
                  {['Strategy', 'Question', 'Category', 'Faithfulness', 'Recall', 'Failure', 'Latency'].map((h) => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left' }}>
                      <span className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em' }}>
                        {h.toUpperCase()}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((run, i) => {
                  const isSelected = selectedRunId === run.run_id
                  const stratKey   = run.pipeline_name
                  const accentMap  = {
                    strategy_a_fixed_chunking:        'var(--strat-a)',
                    strategy_b_semantic_chunking:     'var(--strat-b)',
                    strategy_c_parent_child_chunking: 'var(--strat-c)',
                  }
                  const accent = accentMap[stratKey] || 'var(--text-2)'
                  const shortMap = {
                    strategy_a_fixed_chunking:        'A · Fixed',
                    strategy_b_semantic_chunking:     'B · Semantic',
                    strategy_c_parent_child_chunking: 'C · Parent-Child',
                  }
                  const f = run.metrics?.faithfulness
                  return (
                    <tr
                      key={run.run_id}
                      onClick={() => setSelectedRunId(isSelected ? null : run.run_id)}
                      style={{
                        borderBottom: i < runs.length - 1 ? '1px solid var(--border)' : 'none',
                        cursor: 'pointer',
                        background: isSelected ? 'var(--bg-3)' : 'transparent',
                        borderLeft: isSelected ? `2px solid ${accent}` : '2px solid transparent',
                        transition: 'all 0.1s',
                      }}
                      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-2)' }}
                      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
                    >
                      <td style={{ padding: '11px 14px' }}>
                        <span className="mono" style={{
                          fontSize: 10, fontWeight: 500, color: accent,
                          background: `color-mix(in srgb, ${accent} 12%, transparent)`,
                          border: `1px solid color-mix(in srgb, ${accent} 25%, transparent)`,
                          padding: '2px 8px', borderRadius: 99,
                        }}>
                          {shortMap[stratKey] || stratKey}
                        </span>
                      </td>
                      <td style={{ padding: '11px 14px', maxWidth: 260 }}>
                        <span style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.4 }}>
                          {truncate(run.question, 68)}
                        </span>
                      </td>
                      <td style={{ padding: '11px 14px' }}>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                          {run.category || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '11px 14px' }}>
                        <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: scoreColor(f) }}>
                          {fmtPct(f)}
                        </span>
                      </td>
                      <td style={{ padding: '11px 14px' }}>
                        <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: scoreColor(run.metrics?.context_recall) }}>
                          {fmtPct(run.metrics?.context_recall)}
                        </span>
                      </td>
                      <td style={{ padding: '11px 14px' }}>
                        <Badge type={run.metrics?.failure_source} />
                      </td>
                      <td style={{ padding: '11px 14px' }}>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                          {fmtMs(run.latency_ms)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail panel */}
        {selectedRunId && (
          <RunDetailPanel
            runId={selectedRunId}
            onClose={() => setSelectedRunId(null)}
          />
        )}
      </div>
    </div>
  )
}
