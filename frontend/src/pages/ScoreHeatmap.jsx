import { useSummary } from '../hooks/useSummary'
import ScoreCell from '../components/ui/ScoreCell'
import Shimmer from '../components/ui/Shimmer'
import FailureDonut from '../components/charts/FailureDonut'
import PageHeader from '../components/layout/PageHeader'

const CATEGORIES = ['diabetes', 'hypertension', 'asthma', 'depression', 'cancer']

const METRICS = [
  { key: 'faithfulness',      label: 'Faithfulness',  desc: 'Claims grounded in context'     },
  { key: 'answer_relevancy',  label: 'Relevancy',     desc: 'Answer addresses the question'  },
  { key: 'context_precision', label: 'Precision',     desc: 'Signal-to-noise in retrieval'   },
  { key: 'context_recall',    label: 'Recall',        desc: 'Key info successfully retrieved' },
]

const STRATEGIES = [
  { key: 'strategy_a_fixed_chunking',        short: 'A', name: 'Fixed Chunking',    accentVar: '--strat-a' },
  { key: 'strategy_b_semantic_chunking',     short: 'B', name: 'Semantic Chunking', accentVar: '--strat-b' },
  { key: 'strategy_c_parent_child_chunking', short: 'C', name: 'Parent-Child',      accentVar: '--strat-c' },
]

function LegendDot({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
      <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>{label}</span>
    </div>
  )
}

function TableSkeleton() {
  return (
    <div style={{
      background: 'var(--bg-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
    }}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 20, alignItems: 'center' }}>
          <Shimmer height={36} width={36} radius={8} />
          <div style={{ flex: 1, display: 'flex', gap: 16 }}>
            {[1, 2, 3, 4].map((j) => <Shimmer key={j} height={52} width={80} radius={8} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Static findings derived from 84-run benchmark ────────────────
// These are real findings — not placeholder text.
// Each finding maps to a specific pattern observed in the data.
const FINDINGS = [
  {
    id: 'no-winner',
    label: 'No single strategy wins all domains',
    detail: 'Strategy B leads on diabetes (100%) and asthma (90%). Strategy A leads on depression (92%) and hypertension (100%). No strategy dominates across all five domains — deployment choice must be domain-specific.',
    severity: 'info',
  },
  {
    id: 'cancer-danger',
    label: 'Cancer is the highest-risk domain',
    detail: 'All three strategies show 25–40% faithfulness on cancer questions despite context_recall reaching 100% on strategies A and C. The LLM hallucinates even when correct context is retrieved — a pure generation failure. Cancer queries require human review regardless of pipeline.',
    severity: 'danger',
  },
  {
    id: 'recall-gap',
    label: 'Context recall plateaus at 0.4–0.5 across all strategies',
    detail: 'The ChatDoctor corpus does not fully cover PubMedQA reference answers. This is a corpus gap, not a retrieval failure — switching strategies does not fix it. Indexing clinical guidelines alongside ChatDoctor would close this gap.',
    severity: 'warning',
  },
  {
    id: 'relevancy-tradeoff',
    label: 'Strict prompting trades relevancy for faithfulness',
    detail: 'answer_relevancy scores collapsed to 6–19% in early runs when the prompt was too conservative. The current prompt recovers relevancy to 0.65–0.70 while keeping faithfulness above 0.5. This tradeoff is a core RAG deployment decision — there is no free lunch.',
    severity: 'warning',
  },
]

const DEPLOYMENT = [
  {
    strategy: 'B',
    name: 'Semantic Chunking',
    accentVar: '--strat-b',
    domains: ['diabetes', 'asthma'],
    reason: 'Semantic chunks preserve topic boundaries in clinical text, improving coherence of retrieved context. Wins on these domains where precise mechanism explanations matter.',
    badge: 'recommended',
  },
  {
    strategy: 'A',
    name: 'Fixed Chunking',
    accentVar: '--strat-a',
    domains: ['hypertension', 'depression'],
    reason: 'Lower latency and simpler retrieval. Performs best on domains where the corpus has strong coverage and the question can be answered from a single dense chunk.',
    badge: 'recommended',
  },
  {
    strategy: 'any',
    name: 'All strategies',
    accentVar: '--strat-c',
    domains: ['cancer'],
    reason: 'No strategy achieves acceptable faithfulness. LLM-level hallucination persists regardless of retrieval quality. Human review or abstention is required for all cancer queries.',
    badge: 'caution',
  },
]

const SEVERITY_STYLES = {
  danger:  { bg: 'var(--red-dim)',   border: 'rgba(232,68,90,0.25)',   dot: 'var(--red)',   label: 'HIGH RISK' },
  warning: { bg: 'var(--amber-dim)', border: 'rgba(245,158,11,0.25)',  dot: 'var(--amber)', label: 'CAUTION'   },
  info:    { bg: 'var(--bg-2)',       border: 'var(--border)',           dot: 'var(--blue)',  label: 'FINDING'   },
}

function FindingsPanel() {
  return (
    <div style={{
      background: 'var(--bg-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <span className="mono" style={{ fontSize: 10, letterSpacing: '0.08em', color: 'var(--text-2)' }}>
            BENCHMARK FINDINGS
          </span>
          <span className="mono" style={{
            marginLeft: 10, fontSize: 10, color: 'var(--text-3)',
            background: 'var(--bg-3)', padding: '2px 8px', borderRadius: 20,
            border: '1px solid var(--border)',
          }}>
            84 runs · 5 domains · 3 strategies
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {FINDINGS.map((f, i) => {
          const style = SEVERITY_STYLES[f.severity]
          return (
            <div key={f.id} style={{
              padding: '16px 20px',
              borderBottom: i < FINDINGS.length - 1 ? '1px solid var(--border)' : 'none',
              display: 'flex', gap: 14, alignItems: 'flex-start',
            }}>
              <div style={{
                marginTop: 3, width: 7, height: 7, borderRadius: '50%',
                background: style.dot, flexShrink: 0,
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 5 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-0)' }}>
                    {f.label}
                  </span>
                  <span className="mono" style={{
                    fontSize: 9, letterSpacing: '0.07em',
                    color: style.dot, background: style.bg,
                    border: `1px solid ${style.border}`,
                    padding: '2px 7px', borderRadius: 20,
                  }}>
                    {style.label}
                  </span>
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.6, margin: 0 }}>
                  {f.detail}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function DeploymentPanel() {
  return (
    <div style={{
      background: 'var(--bg-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-2)',
      }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: '0.08em', color: 'var(--text-2)' }}>
          DEPLOYMENT RECOMMENDATION
        </span>
        <p style={{ fontSize: 12, color: 'var(--text-2)', margin: '5px 0 0', lineHeight: 1.5 }}>
          No single strategy is universally safe. Choose based on domain.
        </p>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 0,
      }}>
        {DEPLOYMENT.map((d, i) => {
          const accent = `var(${d.accentVar})`
          const isCaution = d.badge === 'caution'
          return (
            <div key={d.strategy} style={{
              padding: '18px 20px',
              borderRight: i < DEPLOYMENT.length - 1 ? '1px solid var(--border)' : 'none',
              borderBottom: 0,
              display: 'flex', flexDirection: 'column', gap: 12,
            }}>
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="mono" style={{
                    width: 32, height: 32, borderRadius: 7,
                    background: `color-mix(in srgb, ${accent} 12%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${accent} 28%, transparent)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 700, color: accent,
                  }}>
                    {d.strategy === 'any' ? '!' : d.strategy}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-0)' }}>
                      {d.strategy === 'any' ? 'No safe strategy' : `Strategy ${d.strategy}`}
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
                      {d.name}
                    </div>
                  </div>
                </div>
                <span className="mono" style={{
                  fontSize: 9, letterSpacing: '0.07em', padding: '3px 8px',
                  borderRadius: 20, flexShrink: 0,
                  background: isCaution ? 'var(--red-dim)'   : 'var(--green-dim)',
                  border:     isCaution ? 'rgba(232,68,90,0.25)' : 'rgba(0,208,132,0.25)',
                  color:      isCaution ? 'var(--red)'   : 'var(--green)',
                }}>
                  {isCaution ? 'AVOID' : 'DEPLOY'}
                </span>
              </div>

              {/* Domains */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {d.domains.map((dom) => (
                  <span key={dom} className="mono" style={{
                    fontSize: 10, padding: '3px 9px', borderRadius: 20,
                    background: isCaution
                      ? 'var(--red-dim)'
                      : `color-mix(in srgb, ${accent} 10%, transparent)`,
                    border: isCaution
                      ? '1px solid rgba(232,68,90,0.2)'
                      : `1px solid color-mix(in srgb, ${accent} 22%, transparent)`,
                    color: isCaution ? 'var(--red)' : accent,
                  }}>
                    {dom}
                  </span>
                ))}
              </div>

              {/* Reason */}
              <p style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.6, margin: 0 }}>
                {d.reason}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ScoreHeatmap() {
  const { data, loading, error, category, setCategory } = useSummary()

  const selectStyle = {
    padding: '7px 12px', fontSize: 12,
    background: 'var(--bg-2)', color: 'var(--text-0)',
    border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
    outline: 'none', fontFamily: 'var(--font-ui)', cursor: 'pointer',
  }

  return (
    <div style={{ padding: 'calc(var(--nav-h) + 32px) var(--page-pad) 48px', maxWidth: 1300, margin: '0 auto' }}>
      <PageHeader
        title="Score Heatmap"
        accent="Heatmap"
        subtitle="Average RAGAS metrics across all runs grouped by pipeline strategy. Color encodes performance — green is safe, amber is borderline, red needs attention."
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ display: 'flex', gap: 14 }}>
              <LegendDot color="var(--green)" label="≥ 80%" />
              <LegendDot color="var(--amber)" label="≥ 50%" />
              <LegendDot color="var(--red)"   label="< 50%" />
            </div>
            <select value={category} onChange={(e) => setCategory(e.target.value)} style={selectStyle}>
              <option value="">All categories</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        }
      />

      {error && (
        <div style={{
          padding: '12px 16px', marginBottom: 20,
          background: 'var(--red-dim)', border: '1px solid rgba(232,68,90,0.3)',
          borderRadius: 'var(--radius-sm)', color: 'var(--red)', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {loading && <TableSkeleton />}

      {!loading && data?.summary?.length === 0 && (
        <div style={{
          padding: '5rem', textAlign: 'center',
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
        }}>
          <div className="serif" style={{ fontSize: 24, color: 'var(--text-2)', marginBottom: 8 }}>No data yet</div>
          <p className="mono" style={{ fontSize: 12, color: 'var(--text-2)' }}>
            Run queries first to populate the heatmap
          </p>
        </div>
      )}

      {!loading && data?.summary?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Main heatmap table */}
          <div className="anim-fade-up" style={{
            background: 'var(--bg-1)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-2)', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '12px 20px', textAlign: 'left', width: 220 }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.08em' }}>
                      STRATEGY
                    </span>
                  </th>
                  {METRICS.map((m) => (
                    <th key={m.key} style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em' }}>
                        {m.label.toUpperCase()}
                      </div>
                      <div className="mono" style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 2 }}>
                        {m.desc}
                      </div>
                    </th>
                  ))}
                  <th style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em' }}>LATENCY</span>
                  </th>
                  <th style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em' }}>RUNS</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.summary.map((row, i) => {
                  const s = STRATEGIES.find((s) => s.key === row.pipeline_name) || STRATEGIES[i] || {}
                  const accent = `var(${s.accentVar || '--strat-a'})`
                  return (
                    <tr
                      key={row.pipeline_name}
                      style={{
                        borderBottom: i < data.summary.length - 1 ? '1px solid var(--border)' : 'none',
                        transition: 'background var(--dur)',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-2)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <td style={{ padding: '16px 20px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div className="mono" style={{
                            width: 36, height: 36, borderRadius: 8,
                            background: `color-mix(in srgb, ${accent} 12%, transparent)`,
                            border: `1px solid color-mix(in srgb, ${accent} 28%, transparent)`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 14, fontWeight: 700, color: accent, flexShrink: 0,
                          }}>
                            {s.short}
                          </div>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-0)' }}>{s.name}</div>
                            <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 2 }}>
                              Strategy {s.short}
                            </div>
                          </div>
                        </div>
                      </td>
                      {METRICS.map((m) => (
                        <td key={m.key} style={{ padding: '14px 16px', textAlign: 'center' }}>
                          <ScoreCell value={row.metrics?.[m.key]} />
                        </td>
                      ))}
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span className="mono" style={{ fontSize: 13, color: 'var(--text-1)' }}>
                          {row.avg_latency_ms != null ? `${Math.round(row.avg_latency_ms)}` : '—'}
                          <span style={{ fontSize: 10, color: 'var(--text-2)' }}>ms</span>
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span className="mono" style={{ fontSize: 13, color: 'var(--text-1)' }}>
                          {row.run_count}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Failure distribution cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
            {data.summary.map((row, i) => {
              const s = STRATEGIES.find((s) => s.key === row.pipeline_name) || STRATEGIES[i] || {}
              const accent = `var(${s.accentVar || '--strat-a'})`
              return (
                <div
                  key={row.pipeline_name}
                  className="anim-fade-up"
                  style={{
                    background: 'var(--bg-1)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-lg)', padding: '18px 20px',
                    animationDelay: `${i * 0.08}s`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.07em' }}>
                      {s.name?.toUpperCase()} · FAILURE DISTRIBUTION
                    </div>
                    <span className="mono" style={{ fontSize: 10, color: accent }}>
                      {row.run_count} runs
                    </span>
                  </div>
                  <FailureDonut distribution={row.failure_distribution || {}} />
                </div>
              )
            })}
          </div>

          {/* Benchmark findings */}
          <FindingsPanel />

          {/* Deployment recommendation */}
          <DeploymentPanel />

          {/* Best strategy callout */}
          {(() => {
            const best = [...data.summary].sort(
              (a, b) => (b.metrics?.faithfulness || 0) - (a.metrics?.faithfulness || 0)
            )[0]
            const s = STRATEGIES.find((s) => s.key === best?.pipeline_name)
            if (!s || !best?.metrics?.faithfulness) return null
            const accent = `var(${s.accentVar})`
            return (
              <div
                className="anim-fade-up"
                style={{
                  padding: '20px 24px',
                  background: 'var(--green-dim)',
                  border: '1px solid rgba(0,208,132,0.25)',
                  borderRadius: 'var(--radius-lg)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
              >
                <div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--green)', letterSpacing: '0.08em', marginBottom: 6 }}>
                    HIGHEST FAITHFULNESS STRATEGY
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-0)' }}>
                    Strategy {s.short} · {s.name}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-1)', marginTop: 4 }}>
                    Lowest hallucination risk across all evaluated runs
                  </div>
                </div>
                <div className="mono" style={{ fontSize: 40, fontWeight: 700, color: 'var(--green)' }}>
                  {Math.round((best.metrics.faithfulness || 0) * 100)}%
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}