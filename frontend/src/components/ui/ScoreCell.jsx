import { scoreColor, scoreDimBg, fmtPct } from '../../utils/format'

export default function ScoreCell({ value }) {
  const color = scoreColor(value)
  const bg    = scoreDimBg(value)
  const pct   = value != null ? Math.round(value * 100) : 0

  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 5,
        padding: '8px 18px',
        background: bg,
        border: `1px solid ${value != null ? color : 'var(--border)'}22`,
        borderRadius: 'var(--radius-md)',
        minWidth: 76,
      }}
    >
      <span className="mono" style={{ fontSize: 18, fontWeight: 600, color, lineHeight: 1 }}>
        {fmtPct(value)}
      </span>
      <div style={{ height: 2, width: 36, background: 'var(--bg-4)', borderRadius: 99 }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: color,
            borderRadius: 99,
            transition: 'width 1s var(--ease)',
          }}
        />
      </div>
    </div>
  )
}