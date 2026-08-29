import { cn } from '@/lib/utils'

export interface KeyValueItem {
  key: React.ReactNode
  value: React.ReactNode
  /** Renders the value as a contrast link tone (prototype .v.link). */
  link?: boolean
}

/** Prototype .kv — the key/value list used in detail right rails. */
export function KeyValueList({
  items,
  className,
}: {
  items: readonly KeyValueItem[]
  className?: string
}) {
  return (
    <ul className={cn('kv', className)}>
      {items.map((item, index) => (
        <li key={index}>
          <span className="k">{item.key}</span>
          <span className={cn('v', item.link && 'link')}>{item.value}</span>
        </li>
      ))}
    </ul>
  )
}
