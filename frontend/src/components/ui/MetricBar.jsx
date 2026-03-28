import { fmtPct, scoreColor } from '../../utils/format'

export default function MetricBar({ label, value, accent }) {
  const pct   = value != null ? Math.round(value * 100) : 0
  const color = scoreColor(value)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 38px', alignItems: 'center', gap: 10 }}>
      <span
        className="mono"
        style={{ fontSize: 11, color: 'var(--text-1)', letterSpacing: '0.03em', whiteSpace: 'nowrap' }}
      >
        {label}
      </span>

      <div style={{ height: 3, background: 'var(--bg-4)', borderRadius: 99, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: color,
            borderRadius: 99,
            transition: 'width 1.2s var(--ease)',
            boxShadow: value != null ? `0 0 6px ${color}55` : 'none',
          }}
        />
      </div>

      <span className="mono" style={{ fontSize: 12, fontWeight: 600, color, textAlign: 'right' }}>
        {fmtPct(value)}
      </span>
    </div>
  )
}