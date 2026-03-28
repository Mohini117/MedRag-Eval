export default function PageHeader({ title, accent, subtitle, right }) {
  const parts = title.split(accent)
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 28 }}>
      <div className="anim-fade-up">
        <h1 className="serif" style={{ fontSize: 36, lineHeight: 1.1, marginBottom: 6 }}>
          {parts[0]}
          {accent && <em style={{ color: 'var(--green)', fontStyle: 'italic' }}>{accent}</em>}
          {parts[1]}
        </h1>
        {subtitle && (
          <p style={{ fontSize: 13, color: 'var(--text-1)', maxWidth: 560 }}>{subtitle}</p>
        )}
      </div>
      {right && <div>{right}</div>}
    </div>
  )
}