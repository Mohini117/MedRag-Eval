import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Query Runner', icon: 'Q' },
  { to: '/benchmark', label: 'Benchmark Results', icon: 'B' },
  { to: '/heatmap', label: 'Score Heatmap', icon: 'H' },
  { to: '/failure', label: 'Failure Explorer', icon: 'F' },
  { to: '/trace', label: 'Trace Viewer', icon: 'T' },
]

const navStyle = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  zIndex: 200,
  height: 'var(--nav-h)',
  background: 'rgba(9, 11, 14, 0.88)',
  backdropFilter: 'blur(14px)',
  borderBottom: '1px solid var(--border)',
  display: 'flex',
  alignItems: 'center',
  padding: '0 var(--page-pad)',
  gap: 0,
}

export default function NavBar() {
  return (
    <nav style={navStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginRight: 40 }}>
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: 'var(--bg-2)',
            border: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 12 L5 5 L8.5 9.5 L11 5.5 L14 12" stroke="var(--green)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="8.5" cy="9.5" r="1.2" fill="var(--green)" opacity="0.5" />
          </svg>
        </div>
        <div>
          <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-0)', letterSpacing: '0.02em' }}>
            MedRAG<span style={{ color: 'var(--green)' }}>.</span>Eval
          </div>
          <div className="mono" style={{ fontSize: 9, color: 'var(--text-2)', letterSpacing: '0.1em' }}>
            HALLUCINATION BENCHMARK
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 2, flex: 1 }}>
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--text-0)' : 'var(--text-1)',
              background: isActive ? 'var(--bg-3)' : 'transparent',
              border: isActive ? '1px solid var(--border-hi)' : '1px solid transparent',
              transition: 'all var(--dur) var(--ease)',
              textDecoration: 'none',
              letterSpacing: '0.01em',
            })}
          >
            <span style={{ fontSize: 10, opacity: 0.6 }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </div>

      <div className="mono" style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.07em', display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ color: 'var(--green)', animation: 'pulse 2.5s infinite' }}>o</span>
        API LIVE
      </div>
    </nav>
  )
}
