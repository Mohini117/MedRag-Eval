import { useState } from 'react'
import { useRunQuery } from '../hooks/userRunQuery'
import Badge from '../components/ui/Badge'
import MetricBar from '../components/ui/MetricBar'
import RiskGauge from '../components/ui/RiskGauge'
import Shimmer from '../components/ui/Shimmer'
import PageHeader from '../components/layout/PageHeader'
import { fmtMs } from '../utils/format'

const STRATEGIES = [
  { key: 'strategy_a_fixed_chunking', short: 'A', name: 'Fixed Chunking', accentVar: '--strat-a' },
  { key: 'strategy_b_semantic_chunking', short: 'B', name: 'Semantic Chunking', accentVar: '--strat-b' },
  { key: 'strategy_c_parent_child_chunking', short: 'C', name: 'Parent-Child', accentVar: '--strat-c' },
]

const METRICS = [
  { key: 'faithfulness', label: 'Faithfulness' },
  { key: 'answer_relevancy', label: 'Relevancy' },
  { key: 'context_precision', label: 'Precision' },
  { key: 'context_recall', label: 'Recall' },
]

const CATEGORIES = ['diabetes', 'hypertension', 'asthma', 'depression', 'cancer']

function StrategyCard({ result, accentVar, short, name }) {
  const accent = `var(${accentVar})`
  const metrics = result.metrics || {}
  const hasError = Boolean(result.error)

  return (
    <div
      className="anim-fade-up"
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--border)',
        borderTop: `2px solid ${accent}`,
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            className="mono"
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: `color-mix(in srgb, ${accent} 15%, transparent)`,
              border: `1px solid color-mix(in srgb, ${accent} 30%, transparent)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
              fontWeight: 700,
              color: accent,
            }}
          >
            {short}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{name}</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
              {result.latency_ms != null ? fmtMs(result.latency_ms) : '-'} | {result.contexts?.length || 0} chunks
            </div>
          </div>
        </div>
        <Badge type={result.failure_source || (hasError ? 'partial' : null)} />
      </div>

      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 6 }}>
          {hasError ? 'PIPELINE ERROR' : 'GENERATED ANSWER'}
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.65 }}>
          {result.error || result.answer || 'No answer returned.'}
        </p>
      </div>

      <div
        style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          gap: 16,
          alignItems: 'center',
        }}
      >
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {METRICS.map((metric) => (
            <MetricBar key={metric.key} label={metric.label} value={metrics[metric.key]} />
          ))}
        </div>
        <RiskGauge value={metrics.faithfulness} size={90} />
      </div>

      <div style={{ padding: '12px 18px', flex: 1 }}>
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 8 }}>
          CLAIM ANALYSIS | {result.claims?.length || 0} claims
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {!result.claims?.length && (
            <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
              {hasError ? 'Claim analysis skipped because the pipeline failed.' : 'No claim analysis returned for this run.'}
            </div>
          )}
          {(result.claims || []).map((claim, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'flex-start',
                padding: '7px 10px',
                background:
                  claim.status === 'hallucinated'
                    ? 'var(--red-dim)'
                    : claim.status === 'supported'
                    ? 'var(--green-dim)'
                    : 'var(--amber-dim)',
                borderRadius: 6,
                border: `1px solid ${
                  claim.status === 'hallucinated'
                    ? 'rgba(232,68,90,0.2)'
                    : claim.status === 'supported'
                    ? 'rgba(0,208,132,0.2)'
                    : 'rgba(245,166,35,0.2)'
                }`,
              }}
            >
              <Badge type={claim.status} />
              <span style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.5, flex: 1 }}>
                {claim.claim_text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function SkeletonCard({ accentVar }) {
  const accent = `var(${accentVar})`
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--border)',
        borderTop: `2px solid ${accent}`,
        borderRadius: 'var(--radius-lg)',
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <Shimmer height={34} width={34} radius={8} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Shimmer height={14} width={120} />
          <Shimmer height={10} width={80} />
        </div>
      </div>
      <Shimmer height={60} />
      {[1, 2, 3, 4].map((item) => (
        <Shimmer key={item} height={8} width={`${50 + item * 10}%`} />
      ))}
    </div>
  )
}

export default function QueryRunner() {
  const [question, setQuestion] = useState('Does metformin reduce blood sugar in type 2 diabetes?')
  const [reference, setReference] = useState(
    'Metformin is a first-line treatment for type 2 diabetes that works by reducing hepatic glucose production and improving insulin sensitivity.'
  )
  const [category, setCategory] = useState('diabetes')
  const { data, loading, error, elapsed, execute } = useRunQuery()

  const orderedResults = STRATEGIES.map((strategy) => (
    data?.results?.find((result) => result.pipeline_name === strategy.key) || {
      pipeline_name: strategy.key,
      run_id: strategy.key,
      answer: null,
      contexts: [],
      metrics: {},
      claims: [],
      failure_source: null,
      latency_ms: null,
      error: null,
    }
  ))

  const handleRun = () => {
    execute({ question, reference_answer: reference, category })
  }

  const inputStyle = {
    width: '100%',
    padding: '10px 12px',
    resize: 'vertical',
    lineHeight: 1.65,
    fontSize: 13,
    color: 'var(--text-0)',
    background: 'var(--bg-3)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    outline: 'none',
  }

  const labelStyle = {
    display: 'block',
    fontSize: 10,
    fontWeight: 500,
    color: 'var(--text-2)',
    letterSpacing: '0.08em',
    marginBottom: 7,
    fontFamily: 'var(--font-mono)',
  }

  return (
    <div style={{ padding: 'calc(var(--nav-h) + 32px) var(--page-pad) 48px', maxWidth: 1300, margin: '0 auto' }}>
      <PageHeader
        title="Medical RAG Hallucination"
        accent="Hallucination"
        subtitle="Submit a clinical question. All three chunking strategies run simultaneously and return retrieval, answer, and claim-level analysis."
        right={
          <div style={{ display: 'flex', gap: 10 }}>
            {STRATEGIES.map((strategy) => (
              <div
                key={strategy.key}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  padding: '10px 14px',
                  background: 'var(--bg-1)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div
                  className="mono"
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: `color-mix(in srgb, var(${strategy.accentVar}) 15%, transparent)`,
                    border: `1px solid color-mix(in srgb, var(${strategy.accentVar}) 30%, transparent)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    fontWeight: 700,
                    color: `var(${strategy.accentVar})`,
                  }}
                >
                  {strategy.short}
                </div>
                <span className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.08em' }}>
                  {strategy.name.split(' ')[0]}
                </span>
              </div>
            ))}
          </div>
        }
      />

      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          padding: 24,
          marginBottom: 28,
        }}
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
          <div>
            <label style={labelStyle}>CLINICAL QUESTION</label>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>
              REFERENCE ANSWER <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>| ground truth for RAGAS recall</span>
            </label>
            <textarea value={reference} onChange={(event) => setReference(event.target.value)} rows={3} style={inputStyle} />
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div>
            <label style={labelStyle}>CATEGORY</label>
            <select value={category} onChange={(event) => setCategory(event.target.value)} style={{ ...inputStyle, width: 'auto', padding: '8px 12px' }}>
              {CATEGORIES.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </div>

          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              marginTop: 22,
              padding: '9px 28px',
              background: loading ? 'var(--bg-4)' : 'var(--green)',
              color: loading ? 'var(--text-2)' : 'var(--bg-0)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              fontSize: 13,
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.05em',
              transition: 'all var(--dur) var(--ease)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {loading ? `RUNNING | ${elapsed}s` : 'RUN BENCHMARK ->'}
          </button>

          {!loading && !data && (
            <p className="mono" style={{ marginTop: 22, fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.04em' }}>
              Runs 3 pipelines | RAGAS | DeepEval | about 60-120s
            </p>
          )}
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 16px',
            marginBottom: 20,
            background: 'var(--red-dim)',
            border: '1px solid rgba(232,68,90,0.3)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--red)',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {STRATEGIES.map((strategy) => (
            <SkeletonCard key={strategy.key} accentVar={strategy.accentVar} />
          ))}
        </div>
      )}

      {data?.results && (
        <>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 18 }}>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.08em' }}>
              RESULTS
            </span>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            <span className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
              {orderedResults.filter((result) => result.answer || result.error).length} strategies evaluated
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
            {orderedResults.map((result, index) => {
              const strategy = STRATEGIES.find((item) => item.key === result.pipeline_name) || STRATEGIES[index]
              return (
                <StrategyCard
                  key={result.run_id || result.pipeline_name}
                  result={result}
                  accentVar={strategy?.accentVar || '--strat-a'}
                  short={strategy?.short || '?'}
                  name={strategy?.name || result.pipeline_name}
                />
              )
            })}
          </div>

          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              padding: '20px 24px',
            }}
          >
            <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 16 }}>
              FAITHFULNESS COMPARISON
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
              {orderedResults.map((result, index) => {
                const strategy = STRATEGIES.find((item) => item.key === result.pipeline_name) || STRATEGIES[index]
                const accent = `var(${strategy?.accentVar || '--strat-a'})`
                const faithfulness = result.metrics?.faithfulness
                const pct = faithfulness != null ? Math.round(faithfulness * 100) : 0

                return (
                  <div key={result.run_id || result.pipeline_name}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-1)' }}>{strategy?.name}</span>
                      <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: accent }}>
                        {faithfulness != null ? `${pct}%` : '-'}
                      </span>
                    </div>
                    <div style={{ height: 5, background: 'var(--bg-4)', borderRadius: 99, overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${pct}%`,
                          background: accent,
                          borderRadius: 99,
                          boxShadow: `0 0 8px color-mix(in srgb, ${accent} 60%, transparent)`,
                          transition: 'width 1.4s var(--ease)',
                        }}
                      />
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 4 }}>
                      {result.error
                        ? 'warning: pipeline error'
                        : result.failure_source === 'none'
                        ? 'ok: no failure detected'
                        : `warning: failure = ${result.failure_source}`}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
