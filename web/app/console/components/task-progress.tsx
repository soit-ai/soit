/** Prototype .progress — track bar + mono caption for task rows. */
export function TaskProgress({ pct, label }: { pct: number; label: React.ReactNode }) {
  return (
    <span className="progress">
      <span className="track">
        <i style={{ width: `${pct}%` }} />
      </span>
      <em>{label}</em>
    </span>
  )
}
