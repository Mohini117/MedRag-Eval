import { useState } from 'react'
import { useRuns, useRunDetail } from '../hooks/useRuns'
import Badge from '../components/ui/Badge'
import Shimmer from '../components/ui/Shimmer'
import PageHeader from '../components/layout/PageHeader'
import { fmtPct, fmtMs, fmtTime, truncate, scoreColor } from '../utils/format'

const METRICS = [
  { key: 'faithfulness',      label: 'Faithfulness',  desc: 'Claims grounded in context'      },
  { key: 'answer_relevancy',  label: 'Relevancy',     desc: 'Answer addresses the question'   },
  { key: 'context_precision', label: 'Precision',     desc: 'Signal-to-noise in retrieval'    },
  { key: 'context_recall',    label: 'Recall',        desc: 'Key info successfully retrieved' },
]

const ACCENT_MAP = {
  strategy_a_fixed_chunking:        'var(--strat-a)',
  strategy_b_semantic_chunking:     'var(--strat-b)',
  strategy_c_parent_child_chunking: 'var(--strat-c)',
}
const SHORT_MAP = {
  strategy_a_fixed_chunking:        { short: 'A', name: 'Fixed Chunking'    },
  strategy_b_semantic_chunking:     { short: 'B', name: 'Semantic Chunking' },
  strategy_c_parent_child_chunking: { short: 'C', name: 'Parent-Child'      },
}

function RunListItem({ run, isSelected, onClick }) {
  const accent = ACCENT_MAP[run.pipeline_name] || 'var(--text-2)'
  const info   = SHORT_MAP[run.pipeline_name]  || { short: '?', name: run.pipeline_name }
  const f      = run.metrics?.faithfulness

  return (
    <div
      onClick={onClick}
      style={{
        padding: '13px 16px',
        cursor: 'pointer',
        borderBottom: '1px solid var(--border)',
        background: isSelected ? 'var(--bg-3)' : 'transparent',
        borderLeft: isSelected ? `2px solid ${accent}` : '2px solid transparent',
        transition: 'all 0.1s',
      }}
      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-2)' }}
      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
        <span className="mono" style={{
          fontSize: 10, fontWeight: 600, color: accent,
          background: `color-mix(in srgb, ${accent} 12%, transparent)`,
          border: `1px solid color-mix(in srgb, ${accent} 25%, transparent)`,
          padding: '2px 8px', borderRadius: 99,
        }}>
          {info.short} · {info.name}
        </span>
        <Badge type={run.metrics?.failure_source} />
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-1)', margin: '0 0 5px', lineHeight: 1.45 }}>
        {truncate(run.question, 72)}
      </p>
      <div style={{ display: 'flex', gap: 12 }}>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
          F:{' '}
          <span style={{ color: scoreColor(f), fontWeight: 600 }}>
            {fmtPct(f)}
          </span>
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
          {fmtTime(run.created_at)}
        </span>
      </div>
    </div>
  )
}

function MetricTile({ label, desc, value }) {
  const color = scoreColor(value)
  const dimBg = value == null
    ? 'var(--bg-3)'
    : value >= 0.8
    ? 'var(--green-dim)'
    : value >= 0.5
    ? 'var(--amber-dim)'
    : 'var(--red-dim)'

  return (
    <div style={{
      padding: '14px 16px', background: dimBg,
      borderRadius: 'var(--radius-md)',
      border: `1px solid ${value != null ? color : 'var(--border)'}22`,
    }}>
      <div className="mono" style={{ fontSize: 9, color, opacity: 0.7, letterSpacing: '0.07em', marginBottom: 7 }}>
        {label.toUpperCase()}
      </div>
      <div className="mono" style={{ fontSize: 26, fontWeight: 700, color, lineHeight: 1 }}>
        {fmtPct(value)}
      </div>
      <div className="mono" style={{ fontSize: 9, color, opacity: 0.5, marginTop: 5 }}>{desc}</div>
    </div>
  )
}

function ContextChunk({ context, index }) {
  const [expanded, setExpanded] = useState(false)
  const preview = truncate(context, 220)
  const hasMore = context?.length > 220

  return (
    <div style={{
      padding: '12px 14px',
      background: 'var(--bg-2)',
      borderRadius: 'var(--radius-md)',
      borderLeft: '3px solid var(--teal)',
    }}>
      <div className="mono" style={{ fontSize: 9, color: 'var(--teal)', marginBottom: 6, opacity: 0.8 }}>
        CONTEXT [{index}]
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.65, margin: 0 }}>
        {expanded ? context : preview}
      </p>
      {hasMore && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--teal)', fontSize: 11, marginTop: 6, padding: 0,
            fontFamily: 'var(--font-mono)',
          }}
        >
          {expanded ? '↑ show less' : '↓ show more'}
        </button>
      )}
    </div>
  )
}

function TraceDetail({ runId }) {
  const { data, loading } = useRunDetail(runId)
  const accent = ACCENT_MAP[data?.pipeline_name] || 'var(--text-2)'
  const info   = SHORT_MAP[data?.pipeline_name]  || { short: '?', name: '' }

  if (loading) {
    return (
      <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Shimmer height={30} width={160} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {[1,2,3,4].map((i) => <Shimmer key={i} height={80} />)}
        </div>
        <Shimmer height={100} />
        <Shimmer height={60} />
        <Shimmer height={60} />
        <Shimmer height={60} />
      </div>
    )
  }

  if (!data) return null

  return (
    <div style={{ padding: '28px', overflowY: 'auto', height: '100%' }}>
      {/* Run header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 22 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 5 }}>
            <div className="mono" style={{
              width: 32, height: 32, borderRadius: 7,
              background: `color-mix(in srgb, ${accent} 14%, transparent)`,
              border: `1px solid color-mix(in srgb, ${accent} 28%, transparent)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, fontWeight: 700, color: accent,
            }}>
              {info.short}
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-0)' }}>{info.name}</div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
                {fmtMs(data.latency_ms)} · {data.trace?.context_count || 0} contexts retrieved
              </div>
            </div>
          </div>
        </div>
        <Badge type={data.metrics?.failure_source} size="md" />
      </div>

      {/* Metric tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 24 }}>
        {METRICS.map((m) => (
          <MetricTile key={m.key} label={m.label} desc={m.desc} value={data.metrics?.[m.key]} />
        ))}
      </div>

      {/* Failure diagnosis */}
      {data.metrics?.failure_source && data.metrics.failure_source !== 'none' && (
        <div style={{
          padding: '12px 16px', marginBottom: 20,
          background: data.metrics.failure_source === 'retrieval' ? 'var(--red-dim)' : 'var(--amber-dim)',
          border: `1px solid ${data.metrics.failure_source === 'retrieval' ? 'rgba(232,68,90,0.25)' : 'rgba(245,166,35,0.25)'}`,
          borderRadius: 'var(--radius-md)',
        }}>
          <div className="mono" style={{
            fontSize: 10, letterSpacing: '0.07em', marginBottom: 4,
            color: data.metrics.failure_source === 'retrieval' ? 'var(--red)' : 'var(--amber)',
          }}>
            {data.metrics.failure_source === 'retrieval' ? '⚠ RETRIEVAL FAILURE' : '⚠ LLM GENERATION FAILURE'}
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-1)', margin: 0 }}>
            {data.metrics.failure_source === 'retrieval'
              ? `Context recall is ${fmtPct(data.metrics.context_recall)} — the retrieval system failed to surface the key information needed to answer this question accurately.`
              : `Context recall is sufficient (${fmtPct(data.metrics.context_recall)}) but faithfulness is low (${fmtPct(data.metrics.faithfulness)}) — the LLM generated claims not supported by the retrieved context.`}
          </p>
        </div>
      )}

      {/* Question */}
      <div style={{ marginBottom: 18 }}>
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 8 }}>
          QUESTION
        </div>
        <p style={{ fontSize: 14, color: 'var(--text-0)', lineHeight: 1.7 }}>{data.question}</p>
      </div>

      {/* Answer */}
      <div style={{ marginBottom: 24 }}>
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 8 }}>
          GENERATED ANSWER
        </div>
        <div style={{
          padding: '14px 16px', background: 'var(--bg-2)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
          borderLeft: '3px solid var(--blue)',
        }}>
          <p style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.7, margin: 0 }}>{data.answer}</p>
        </div>
      </div>

      {/* Retrieved contexts */}
      {data.trace?.retrieved_contexts?.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 10 }}>
            RETRIEVED CONTEXTS · {data.trace.context_count}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.trace.retrieved_contexts.map((ctx, i) => (
              <ContextChunk key={i} context={ctx} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Claim analysis */}
      {data.claims?.length > 0 && (
        <div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 10 }}>
            CLAIM ANALYSIS · {data.claims.length} claims verified
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.claims.map((c, i) => {
              const color = c.status === 'hallucinated' ? 'var(--red)' : c.status === 'supported' ? 'var(--green)' : 'var(--amber)'
              const dimBg = c.status === 'hallucinated' ? 'var(--red-dim)' : c.status === 'supported' ? 'var(--green-dim)' : 'var(--amber-dim)'
              return (
                <div key={i} style={{
                  display: 'flex', gap: 12, alignItems: 'flex-start',
                  padding: '10px 14px', background: dimBg,
                  borderRadius: 'var(--radius-md)', borderLeft: `3px solid ${color}`,
                }}>
                  <div style={{ paddingTop: 1, flexShrink: 0 }}>
                    <Badge type={c.status} />
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.6, margin: 0, flex: 1 }}>
                    {c.claim_text}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default function TraceViewer() {
  const [selectedRunId, setSelectedRunId] = useState(null)
  const { runs, loading } = useRuns({ limit: 50 })

  return (
    <div style={{ paddingTop: 'var(--nav-h)', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Page header */}
      <div style={{ padding: '24px var(--page-pad) 0', flexShrink: 0 }}>
        <PageHeader
          title="Trace Viewer"
          accent="Viewer"
          subtitle="Full pipeline execution trace — question → retrieval → generation → claim verification. Includes automated failure diagnosis."
        />
      </div>

      {/* Split layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '340px 1fr',
        flex: 1,
        overflow: 'hidden',
        borderTop: '1px solid var(--border)',
        margin: '0 var(--page-pad)',
        marginBottom: 32,
        background: 'var(--bg-1)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
      }}>
        {/* Sidebar */}
        <div style={{ borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{
            padding: '10px 16px',
            background: 'var(--bg-2)', borderBottom: '1px solid var(--border)',
            flexShrink: 0,
          }}>
            <span className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em' }}>
              RECENT RUNS · {runs.length}
            </span>
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {loading ? (
              <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[1,2,3,4,5,6].map((i) => <Shimmer key={i} height={72} />)}
              </div>
            ) : runs.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center' }}>
                <p className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>No runs yet</p>
              </div>
            ) : (
              runs.map((run) => (
                <RunListItem
                  key={run.run_id}
                  run={run}
                  isSelected={selectedRunId === run.run_id}
                  onClick={() => setSelectedRunId(
                    selectedRunId === run.run_id ? null : run.run_id
                  )}
                />
              ))
            )}
          </div>
        </div>

        {/* Main trace area */}
        <div style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {!selectedRunId ? (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              height: '100%', gap: 12, opacity: 0.5,
            }}>
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="18" stroke="var(--border-hi)" strokeWidth="1.5" strokeDasharray="4 3"/>
                <path d="M12 20 L18 26 L28 14" stroke="var(--text-2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text-2)', letterSpacing: '0.07em' }}>
                SELECT A RUN TO INSPECT
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-2)', textAlign: 'center', maxWidth: 260 }}>
                Click any run in the sidebar to view its full pipeline execution trace
              </p>
            </div>
          ) : (
            <TraceDetail runId={selectedRunId} />
          )}
        </div>
      </div>
    </div>
  )
}
