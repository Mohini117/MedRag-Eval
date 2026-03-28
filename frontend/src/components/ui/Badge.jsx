const VARIANTS = {
  // Failure source
  none:         { color: 'var(--green)', bg: 'var(--green-dim)',  label: 'No Failure' },
  retrieval:    { color: 'var(--red)',   bg: 'var(--red-dim)',    label: 'Retrieval'  },
  llm:          { color: 'var(--amber)', bg: 'var(--amber-dim)',  label: 'LLM'        },
  // Claim status
  supported:    { color: 'var(--green)', bg: 'var(--green-dim)',  label: 'Supported'    },
  hallucinated: { color: 'var(--red)',   bg: 'var(--red-dim)',    label: 'Hallucinated' },
  partial:      { color: 'var(--amber)', bg: 'var(--amber-dim)',  label: 'Partial'      },
  // Strategy
  a:            { color: 'var(--strat-a)', bg: 'var(--blue-dim)', label: 'A · Fixed'        },
  b:            { color: 'var(--strat-b)', bg: 'var(--teal-dim)', label: 'B · Semantic'      },
  c:            { color: 'var(--strat-c)', bg: 'var(--amber-dim)',label: 'C · Parent-Child'  },
}

export default function Badge({ type, label: overrideLabel, size = 'sm' }) {
  const v = VARIANTS[type] || { color: 'var(--text-2)', bg: 'var(--bg-3)', label: type || '—' }
  const label = overrideLabel || v.label
  return (
    <span
      className="mono"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: size === 'sm' ? '2px 8px' : '3px 10px',
        borderRadius: 99,
        fontSize: size === 'sm' ? 10 : 11,
        fontWeight: 500,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
        color: v.color,
        background: v.bg,
        border: `1px solid ${v.color}33`,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  )
}
