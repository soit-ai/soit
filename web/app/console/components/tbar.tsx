import type { CSSProperties } from 'react'

import { BREAKDOWN_COLOR, type MockBreakdownSlice } from '../mocks/observe'
import { cn } from '@/lib/utils'

/** Prototype .tbar — the categorical span-breakdown bar for traces. */
export function TBar({
  slices,
  className,
  style,
}: {
  slices: readonly MockBreakdownSlice[]
  className?: string
  style?: CSSProperties
}) {
  const title = slices.map((slice) => `${slice.kind} ${slice.pct}%`).join(' · ')

  return (
    <span className={cn('tbar', className)} style={style} title={title}>
      {slices.map((slice) => (
        <i
          key={slice.kind}
          style={{ background: BREAKDOWN_COLOR[slice.kind], width: `${slice.pct}%` }}
        />
      ))}
    </span>
  )
}

/** Inline legend square+label, prototype pager legend style. */
export function TBarLegend({ slices }: { slices: readonly MockBreakdownSlice['kind'][] }) {
  return (
    <span style={{ display: 'inline-flex', gap: 12, marginLeft: 14 }}>
      {slices.map((kind) => (
        <span key={kind}>
          <i
            style={{
              display: 'inline-block',
              width: 8,
              height: 8,
              borderRadius: 2,
              background: BREAKDOWN_COLOR[kind],
              marginRight: 5,
              verticalAlign: -1,
            }}
          />
          {kind}
        </span>
      ))}
    </span>
  )
}
