import { useEffect, useState } from 'react'
import {
  getBenchmarkResults,
  getBenchmarkStatus,
  getBenchmarkSummary,
} from '../api/client'
import Badge from '../components/ui/Badge'
import ScoreCell from '../components/ui/ScoreCell'
import FailureDonut from '../components/charts/FailureDonut'
import Shimmer from '../components/ui/Shimmer'
import PageHeader from '../components/layout/PageHeader'
import { fmtMs, truncate } from '../utils/format'

const STRATEGIES = {
  strategy_a_fixed_chunking: { short: 'A', name: 'Fixed Chunking', accentVar: '--strat-a', badge: 'a' },
  strategy_b_semantic_chunking: { short: 'B', name: 'Semantic Chunking', accentVar: '--strat-b', badge: 'b' },
  strategy_c_parent_child_chunking: { short: 'C', name: 'Parent-Child', accentVar: '--strat-c', badge: 'c' },
}

const METRICS = [
  { key: 'faithfulness', label: 'Faithfulness' },
  { key: 'answer_relevancy', label: 'Relevancy' },
  { key: 'context_precision', label: 'Precision' },
  { key: 'context_recall', label: 'Recall' },
]

function StatCard({ label, value, caption }) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 18px',
      }}
    >
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.08em', marginBottom: 8 }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: 30, fontWeight: 700, color: 'var(--text-0)', lineHeight: 1 }}>
        {value}
      </div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 6 }}>
        {caption}
      </div>
    </div>
  )
}

function StrategySummaryCard({ row }) {
  const strategy = STRATEGIES[row.pipeline_name] || { short: '?', name: row.pipeline_name, accentVar: '--text-2', badge: null }
  const accent = `var(${strategy.accentVar})`

  return (
    <div
      className="anim-fade-up"
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--border)',
        borderTop: `2px solid ${accent}`,
        borderRadius: 'var(--radius-lg)',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            {strategy.badge ? <Badge type={strategy.badge} /> : null}
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-0)' }}>{strategy.name}</span>
          </div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)' }}>
            {row.run_count} runs | accuracy {row.verdict_accuracy != null ? `${Math.round(row.verdict_accuracy * 100)}%` : '-'}
          </div>
        </div>
        <div className="mono" style={{ fontSize: 12, color: accent }}>
          abstain {row.abstain_rate != null ? `${Math.round(row.abstain_rate * 100)}%` : '-'}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        {METRICS.map((metric) => (
          <div key={metric.key}>
            <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 6 }}>
              {metric.label.toUpperCase()}
            </div>
            <ScoreCell value={row.metrics?.[metric.key]} />
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 16, alignItems: 'center' }}>
        <FailureDonut distribution={row.failure_distribution || {}} />
        <div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', marginBottom: 6 }}>
            AVERAGE LATENCY
          </div>
          <div className="mono" style={{ fontSize: 24, fontWeight: 700, color: accent }}>
            {row.avg_latency_ms != null ? fmtMs(row.avg_latency_ms) : '-'}
          </div>
        </div>
      </div>
    </div>
  )
}

function ResultRunCard({ result }) {
  const strategy = STRATEGIES[result.pipeline_name] || { short: '?', name: result.pipeline_name, accentVar: '--text-2', badge: null }
  const accent = `var(${strategy.accentVar})`
  const verdict = result.benchmark_eval?.predicted_verdict || 'n/a'
  const verdictOk = result.benchmark_eval?.is_correct

  return (
    <div
      style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--border)',
        borderTop: `2px solid ${accent}`,
        borderRadius: 'var(--radius-md)',
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {strategy.badge ? <Badge type={strategy.badge} /> : null}
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-0)' }}>{strategy.name}</span>
        </div>
        <Badge
          type={verdictOk === true ? 'supported' : verdictOk === false ? 'hallucinated' : 'partial'}
          label={verdictOk == null ? verdict : `${verdict} | ${verdictOk ? 'correct' : 'wrong'}`}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Badge type={result.failure_source || 'partial'} label={`failure: ${result.failure_source || 'n/a'}`} />
        <Badge
          type={result.benchmark_eval?.is_abstained ? 'partial' : 'none'}
          label={result.benchmark_eval?.is_abstained ? 'abstained' : 'answered'}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        <div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 4 }}>FAITHFULNESS</div>
          <div className="mono" style={{ fontSize: 16, color: accent, fontWeight: 700 }}>
            {result.metrics?.faithfulness != null ? `${Math.round(result.metrics.faithfulness * 100)}%` : '-'}
          </div>
        </div>
        <div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 4 }}>LATENCY</div>
          <div className="mono" style={{ fontSize: 16, color: accent, fontWeight: 700 }}>
            {result.latency_ms != null ? fmtMs(result.latency_ms) : '-'}
          </div>
        </div>
      </div>

      <div>
        <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 6 }}>ANSWER</div>
        <p style={{ fontSize: 12, color: 'var(--text-1)', lineHeight: 1.55, margin: 0 }}>
          {truncate(result.answer || result.error || 'No answer returned.', 240)}
        </p>
      </div>
    </div>
  )
}

function BenchmarkSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
          <Shimmer height={18} width="60%" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginTop: 16 }}>
            {[1, 2, 3].map((j) => <Shimmer key={j} height={180} radius={12} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function BenchmarkResults() {
  const [category, setCategory] = useState('')
  const [source, setSource] = useState('')
  const [search, setSearch] = useState('')
  const [data, setData] = useState(null)
  const [summary, setSummary] = useState(null)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [statusResult, summaryResult, resultsResult] = await Promise.all([
          getBenchmarkStatus(),
          getBenchmarkSummary(),
          getBenchmarkResults({ category, source, search, limit: 100 }),
        ])
        if (ignore) return
        setStatus(statusResult)
        setSummary(summaryResult)
        setData(resultsResult)
      } catch (err) {
        if (!ignore) setError(err.message)
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    load()
    return () => { ignore = true }
  }, [category, source, search])

  const categories = summary?.categories_available || []
  const sources = summary?.sources_available || []
  const results = data?.results || []

  const inputStyle = {
    padding: '8px 12px',
    background: 'var(--bg-2)',
    color: 'var(--text-0)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    outline: 'none',
    fontSize: 12,
  }

  return (
    <div style={{ padding: 'calc(var(--nav-h) + 32px) var(--page-pad) 48px', maxWidth: 1380, margin: '0 auto' }}>
      <PageHeader
        title="Benchmark Results"
        accent="Benchmark"
        subtitle="File-backed benchmark view for the frozen test queries. This page reads the generated benchmark JSON so the frontend matches the benchmark runner output."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14, marginBottom: 24 }}>
        <StatCard label="QUESTIONS" value={summary?.total_questions ?? '-'} caption="rows in benchmark_results.json" />
        <StatCard label="RUNS" value={summary?.total_runs ?? '-'} caption="question-strategy evaluations" />
        <StatCard label="COMPLETED" value={status ? `${status.completed}/${status.total}` : '-'} caption="runner progress file" />
        <StatCard label="PROGRESS" value={status?.percent != null ? `${status.percent}%` : '-'} caption={status?.is_complete ? 'benchmark complete' : status?.is_running ? 'benchmark running' : 'idle'} />
      </div>

      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          padding: '14px 18px',
          marginBottom: 20,
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
          alignItems: 'flex-end',
        }}
      >
        <div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 6 }}>CATEGORY</div>
          <select value={category} onChange={(event) => setCategory(event.target.value)} style={inputStyle}>
            <option value="">All categories</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>

        <div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 6 }}>SOURCE</div>
          <select value={source} onChange={(event) => setSource(event.target.value)} style={inputStyle}>
            <option value="">All sources</option>
            {sources.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>

        <div style={{ flex: '1 1 320px' }}>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', marginBottom: 6 }}>QUESTION SEARCH</div>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search benchmark question text"
            style={{ ...inputStyle, width: '100%' }}
          />
        </div>

        <div className="mono" style={{ fontSize: 11, color: 'var(--text-2)', marginLeft: 'auto' }}>
          showing {data?.returned ?? 0} of {data?.total ?? 0}
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

      {loading ? <BenchmarkSkeleton /> : null}

      {!loading && summary?.summary?.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 24 }}>
          {summary.summary.map((row) => (
            <StrategySummaryCard key={row.pipeline_name} row={row} />
          ))}
        </div>
      )}

      {!loading && results.length === 0 && (
        <div style={{ padding: '4rem', textAlign: 'center', background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)' }}>
          <div className="serif" style={{ fontSize: 24, color: 'var(--text-2)', marginBottom: 8 }}>No benchmark rows found</div>
          <p className="mono" style={{ fontSize: 12, color: 'var(--text-2)' }}>
            Generate benchmark results or relax the current filters
          </p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {results.map((item, index) => (
            <div
              key={item.testset_id || `${item.question}-${index}`}
              className="anim-fade-up"
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: '18px 20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 14 }}>
                <div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                    <Badge type="none" label={item.category || 'uncategorized'} />
                    <Badge type="partial" label={item.source || 'unknown source'} />
                    <Badge type="supported" label={`expected: ${item.final_answer || 'n/a'}`} />
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-0)', lineHeight: 1.5 }}>
                    {item.question}
                  </div>
                </div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                  {item.completed_at ? new Date(item.completed_at).toLocaleString() : ''}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
                {(item.results || []).map((result) => (
                  <ResultRunCard key={result.run_id || result.pipeline_name} result={result} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
