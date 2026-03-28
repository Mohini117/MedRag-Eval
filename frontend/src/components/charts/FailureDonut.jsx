import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'

const COLORS = {
  none:      'var(--green)',
  retrieval: 'var(--red)',
  llm:       'var(--amber)',
}

const LABELS = { none: 'No Failure', retrieval: 'Retrieval', llm: 'LLM' }

export default function FailureDonut({ distribution = {}, title }) {
  const data = Object.entries(distribution).map(([name, value]) => ({
    name: LABELS[name] || name,
    value,
    key: name,
  }))

  if (data.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120 }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>No data yet</span>
      </div>
    )
  }

  const total = data.reduce((s, d) => s + d.value, 0)

  return (
    <div>
      {title && (
        <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.07em', marginBottom: 12 }}>
          {title}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ width: 100, height: 100 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={28}
                outerRadius={44}
                paddingAngle={3}
                dataKey="value"
                stroke="none"
              >
                {data.map((entry) => (
                  <Cell key={entry.key} fill={COLORS[entry.key] || 'var(--text-2)'} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-0)',
                }}
                formatter={(v) => [`${v} runs (${Math.round((v / total) * 100)}%)`, '']}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.map((d) => (
            <div key={d.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 2,
                  background: COLORS[d.key] || 'var(--text-2)',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 12, color: 'var(--text-1)' }}>{d.name}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)', marginLeft: 'auto' }}>
                {d.value} · {Math.round((d.value / total) * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}