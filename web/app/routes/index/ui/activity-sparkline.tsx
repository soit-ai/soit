import { cn } from '@/lib/utils'

type ActivitySparklineProps = {
  values: number[]
  lineColor: string
  fillColor: string
  barColor: string
  className?: string
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

export function ActivitySparkline({
  values,
  lineColor,
  fillColor,
  barColor,
  className,
}: ActivitySparklineProps) {
  const normalizedValues = values.length > 0 ? values : [0, 0, 0, 0, 0, 0, 0]
  const max = Math.max(...normalizedValues, 1)
  const denominator = Math.max(normalizedValues.length - 1, 1)

  const points = normalizedValues
    .map((value, index) => {
      const x = (index / denominator) * 100
      const ratio = clamp(value / max, 0, 1)
      const y = 88 - ratio * 56
      return `${x},${y}`
    })
    .join(' ')

  const areaPath = `M 0 88 L ${points.replace(/ /g, ' L ')} L 100 88 Z`

  return (
    <div className={cn('relative h-24 overflow-hidden rounded-[20px] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.82)_0%,rgba(248,250,252,0.72)_100%)] dark:border-slate-800 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.72)_0%,rgba(15,23,42,0.52)_100%)]', className)}>
      <div className="absolute inset-x-0 bottom-0 grid h-full grid-cols-7 items-end gap-1 px-2 pb-2">
        {normalizedValues.map((value, index) => {
          const ratio = clamp(value / max, 0, 1)
          const height = `${Math.max(ratio * 70, 12)}%`

          return (
            <div
              key={`${index}-${value}`}
              className="rounded-t-full"
              style={{
                height,
                backgroundColor: barColor,
              }}
            />
          )
        })}
      </div>

      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d={areaPath} fill={fillColor} />
        <polyline
          fill="none"
          points={points}
          stroke={lineColor}
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}
