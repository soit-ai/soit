import { cn } from '@/lib/utils'

export interface ConsoleTabItem<T extends string = string> {
  id: T
  label: React.ReactNode
  /** Mono count/hint rendered after the label, prototype-style. */
  count?: React.ReactNode
}

/** Prototype .tabs — underlined tab strip with mono counts. */
export function ConsoleTabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: readonly ConsoleTabItem<T>[]
  value: T
  onChange: (id: T) => void
  className?: string
}) {
  return (
    <div className={cn('tabs', className)} role="tablist">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={item.id === value}
          className={cn(item.id === value && 'on')}
          onClick={() => onChange(item.id)}
        >
          {item.label}
          {item.count != null && <span className="mono">{item.count}</span>}
        </button>
      ))}
    </div>
  )
}
