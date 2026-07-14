import type { ComponentType, ReactNode } from 'react'

import { cn } from '@/lib/utils'

type MetricTone = 'blue' | 'green' | 'amber' | 'red' | 'cyan'

export interface MetricStripItem {
  id: string
  label: string
  value: string
  delta?: string
  trend?: number[]
  icon: ComponentType<{ className?: string }>
  tone?: MetricTone
}

interface MetricStripProps {
  items: MetricStripItem[]
  deltaLabel?: ReactNode
  className?: string
}

const toneClassNameMap = {
  blue: {
    icon: 'bg-blue-50 text-blue-600 dark:bg-blue-400/12 dark:text-blue-300',
    line: '#2563eb',
    delta: 'text-emerald-600 dark:text-emerald-300',
  },
  green: {
    icon: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-400/12 dark:text-emerald-300',
    line: '#10b981',
    delta: 'text-emerald-600 dark:text-emerald-300',
  },
  amber: {
    icon: 'bg-amber-50 text-amber-600 dark:bg-amber-400/12 dark:text-amber-300',
    line: '#f97316',
    delta: 'text-emerald-600 dark:text-emerald-300',
  },
  red: {
    icon: 'bg-red-50 text-red-600 dark:bg-red-400/12 dark:text-red-300',
    line: '#ef4444',
    delta: 'text-emerald-600 dark:text-emerald-300',
  },
  cyan: {
    icon: 'bg-cyan-50 text-cyan-600 dark:bg-cyan-400/12 dark:text-cyan-300',
    line: '#06b6d4',
    delta: 'text-emerald-600 dark:text-emerald-300',
  },
} satisfies Record<MetricTone, { icon: string; line: string; delta: string }>

function buildSparklinePath(values: number[]) {
  if (values.length === 0) return ''

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 96
  const height = 30
  const step = values.length > 1 ? width / (values.length - 1) : width

  return values
    .map((value, index) => {
      const x = Number((index * step).toFixed(2))
      const y = Number((height - ((value - min) / range) * height).toFixed(2))
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
}

export function MetricStrip({ items, deltaLabel, className }: MetricStripProps) {
  return (
    <section className={cn('grid overflow-hidden rounded-lg border border-border bg-panel shadow-sm md:grid-cols-2 xl:grid-cols-5', className)}>
      {items.map((item, index) => {
        const tone = toneClassNameMap[item.tone || 'blue']
        const Icon = item.icon
        const path = buildSparklinePath(item.trend || [])

        return (
          <div
            key={item.id}
            className={cn(
              'relative flex min-h-[118px] items-center gap-4 px-6 py-5',
              index > 0 && 'border-t border-border md:border-l md:border-t-0',
              index === 2 && 'xl:border-l',
            )}
          >
            <div className={cn('z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full', tone.icon)}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="z-10 min-w-0 flex-1 xl:pr-24">
              <div className="whitespace-nowrap text-sm font-semibold text-muted-foreground">{item.label}</div>
              <div className="mt-1 whitespace-nowrap text-[28px] font-semibold leading-none text-foreground">{item.value}</div>
              {item.delta ? (
                <div className="mt-3 text-xs font-medium text-muted-foreground">
                  {deltaLabel ? <>{deltaLabel} </> : null}<span className={tone.delta}>{item.delta}</span>
                </div>
              ) : null}
            </div>
            {path ? (
              <svg className="pointer-events-none absolute bottom-7 right-5 hidden h-8 w-20 shrink-0 xl:block 2xl:w-24" viewBox="0 0 96 30" aria-hidden="true">
                <path d={path} fill="none" stroke={tone.line} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              </svg>
            ) : null}
          </div>
        )
      })}
    </section>
  )
}
