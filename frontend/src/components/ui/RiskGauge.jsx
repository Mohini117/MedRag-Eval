import { scoreColor } from '../../utils/format'

export default function RiskGauge({ value, size = 88 }) {
  const pct   = value != null ? Math.round(value * 100) : null
  const color = scoreColor(value)
  const label = pct == null ? '—' : pct >= 80 ? 'SAFE' : pct >= 50 ? 'CAUTION' : 'RISK'

  const r   = size * 0.38
  const cx  = size / 2
  const cy  = size * 0.56
  const circ = Math.PI * r

  // arc from left (180°) sweeping right
  const filled  = pct != null ? (pct / 100) * circ : 0
  const endAngle = Math.PI + filled / r
  const x2 = cx + r * Math.cos(endAngle)
  const y2 = cy + r * Math.sin(endAngle)
  const largeArc = filled / r > Math.PI ? 1 : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
      <svg
        width={size}
        height={size * 0.64}
        viewBox={`0 0 ${size} ${size * 0.64}`}
        overflow="visible"
      >
        {/* Track */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="var(--bg-4)"
          strokeWidth={size * 0.07}
          strokeLinecap="round"
        />
        {/* Fill */}
        {pct != null && (
          <path
            d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
            fill="none"
            stroke={color}
            strokeWidth={size * 0.07}
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 5px ${color}88)`,
              transition: 'all 1.2s var(--ease)',
            }}
          />
        )}
        {/* Center value */}
        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          fill={color}
          style={{ fontFamily: 'var(--font-mono)', fontSize: size * 0.2, fontWeight: 600 }}
        >
          {pct != null ? `${pct}%` : '—'}
        </text>
      </svg>
      <span
        className="mono"
        style={{ fontSize: 9, fontWeight: 600, color, letterSpacing: '0.1em' }}
      >
        {label}
      </span>
    </div>
  )
}