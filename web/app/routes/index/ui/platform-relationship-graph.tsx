import { ArrowRight, Bot, type LucideIcon } from 'lucide-react'

import { useHomeFormatters } from '../hooks/use-home-formatters'
import type { DashboardSummary } from '../hooks/use-home-dashboard'

export type PlatformGraphModule = {
  key: string
  href: string
  icon: LucideIcon
  tone: string
  title: string
  description: string
  value: string
}

type PlatformRelationshipGraphProps = {
  summary: DashboardSummary
  modules: PlatformGraphModule[]
  relationEyebrow: string
  relationDescription: string
  coreLabel: string
  coreTitle: string
  coreDescription: string
  publishedLabel: string
  draftLabel: string
  onOpen: (href: string) => void
}

type PositionedModule = PlatformGraphModule & {
  x: number
  y: number
}

const nodePositions: Record<string, { x: number; y: number }> = {
  knowledge: { x: 24, y: 18 },
  workflow: { x: 76, y: 18 },
  settings: { x: 13, y: 50 },
  models: { x: 87, y: 50 },
  tasks: { x: 27, y: 82 },
  observe: { x: 73, y: 82 },
}

function GraphNode({ node, onOpen }: { node: PositionedModule; onOpen: (href: string) => void }) {
  const Icon = node.icon

  return (
    <button
      type="button"
      onClick={() => onOpen(node.href)}
      className={`group absolute w-[220px] -translate-x-1/2 -translate-y-1/2 rounded-[24px] border border-border/70 bg-elevated/92 p-4 text-left transition-colors hover:border-border dark:bg-slate-950/86 bg-gradient-to-br ${node.tone}`}
      style={{ left: `${node.x}%`, top: `${node.y}%` }}
    >
      <div className="flex items-center justify-between">
        <div className="rounded-2xl bg-panel/86 p-2 dark:bg-slate-900">
          <Icon className="h-4 w-4 text-foreground dark:text-slate-200" />
        </div>
        <ArrowRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5" />
      </div>
      <div className="mt-5 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{node.value}</div>
      <div className="mt-2 text-base font-semibold">{node.title}</div>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">{node.description}</p>
    </button>
  )
}

export function PlatformRelationshipGraph({
  summary,
  modules,
  relationEyebrow,
  relationDescription,
  coreLabel,
  coreTitle,
  coreDescription,
  publishedLabel,
  draftLabel,
  onOpen,
}: PlatformRelationshipGraphProps) {
  const { formatNumber } = useHomeFormatters()

  const positionedModules: PositionedModule[] = modules
    .map((module) => {
      const position = nodePositions[module.key]
      if (!position) {
        return null
      }

      return {
        ...module,
        ...position,
      }
    })
    .filter((module): module is PositionedModule => Boolean(module))

  return (
    <>
      <div className="rounded-[24px] border border-border/70 bg-panel/72 p-4">
        <div className="text-[11px] font-medium uppercase tracking-[0.28em] text-muted-foreground">
          {relationEyebrow}
        </div>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{relationDescription}</p>
      </div>

      <div className="hidden rounded-[28px] border border-border/70 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.1),transparent_26%),radial-gradient(circle_at_center,rgba(15,23,42,0.04),transparent_62%)] p-5 lg:block">
        <div className="relative h-[560px] overflow-hidden rounded-[24px] border border-border/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.76)_0%,rgba(248,250,252,0.84)_100%)] dark:bg-[linear-gradient(180deg,rgba(2,6,23,0.56)_0%,rgba(15,23,42,0.76)_100%)]">
          <div className="absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/20" />
          <div className="absolute left-1/2 top-1/2 h-[280px] w-[280px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/20" />
          <div className="absolute left-1/2 top-1/2 h-[150px] w-[150px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/25" />

          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            {positionedModules.map((node) => (
              <g key={node.key}>
                <line
                  x1="50"
                  y1="50"
                  x2={String(node.x)}
                  y2={String(node.y)}
                  stroke="rgba(71, 85, 105, 0.32)"
                  strokeWidth="0.45"
                  strokeDasharray="2.5 2.5"
                />
                <circle cx={String(node.x)} cy={String(node.y)} r="0.9" fill="rgba(14, 165, 233, 0.65)" />
              </g>
            ))}
          </svg>

          {positionedModules.map((node) => (
            <GraphNode key={node.key} node={node} onOpen={onOpen} />
          ))}

          <button
            type="button"
            onClick={() => onOpen('/agents')}
            className="absolute left-1/2 top-1/2 flex w-[320px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[28px] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(15,23,42,0.98)_0%,rgba(12,74,110,0.96)_100%)] p-6 text-left text-white"
          >
            <div className="flex items-center justify-between">
              <div className="rounded-2xl bg-white/10 p-3">
                <Bot className="h-5 w-5" />
              </div>
              <ArrowRight className="h-4 w-4 text-white/70" />
            </div>
            <div className="mt-6 text-xs uppercase tracking-[0.22em] text-cyan-100/70">{coreLabel}</div>
            <div className="mt-3 text-3xl font-semibold">{coreTitle}</div>
            <p className="mt-3 text-sm leading-6 text-slate-200">{coreDescription}</p>
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl border border-white/10 bg-white/8 p-3">
                <div className="text-white/70">{publishedLabel}</div>
                <div className="mt-1 text-xl font-semibold">{formatNumber(summary.publishedAgents)}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/8 p-3">
                <div className="text-white/70">{draftLabel}</div>
                <div className="mt-1 text-xl font-semibold">{formatNumber(summary.draftAgents)}</div>
              </div>
            </div>
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:hidden">
        <button
          type="button"
          onClick={() => onOpen('/agents')}
          className="rounded-[28px] border border-slate-200/70 bg-[linear-gradient(180deg,rgba(15,23,42,0.98)_0%,rgba(12,74,110,0.96)_100%)] p-5 text-left text-white"
        >
          <div className="flex items-center justify-between">
            <div className="rounded-2xl bg-white/10 p-3">
              <Bot className="h-5 w-5" />
            </div>
            <ArrowRight className="h-4 w-4 text-white/70" />
          </div>
          <div className="mt-5 text-xs uppercase tracking-[0.2em] text-cyan-100/70">{coreLabel}</div>
          <div className="mt-2 text-2xl font-semibold">{coreTitle}</div>
          <p className="mt-2 text-sm leading-6 text-slate-200">{coreDescription}</p>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl border border-white/10 bg-white/8 p-3">
              <div className="text-white/70">{publishedLabel}</div>
              <div className="mt-1 text-xl font-semibold">{formatNumber(summary.publishedAgents)}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/8 p-3">
              <div className="text-white/70">{draftLabel}</div>
              <div className="mt-1 text-xl font-semibold">{formatNumber(summary.draftAgents)}</div>
            </div>
          </div>
        </button>

        <div className="grid gap-4 sm:grid-cols-2">
          {modules.map((module) => {
            const Icon = module.icon

            return (
              <button
                key={module.key}
                type="button"
                onClick={() => onOpen(module.href)}
                className={`rounded-[24px] border border-slate-200/70 bg-white/90 p-4 text-left dark:border-slate-800 dark:bg-slate-950/80 bg-gradient-to-br ${module.tone}`}
              >
                <div className="flex items-center justify-between">
                  <div className="rounded-2xl bg-slate-100 p-2 dark:bg-slate-900">
                    <Icon className="h-4 w-4 text-slate-700 dark:text-slate-200" />
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-400" />
                </div>
                <div className="mt-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{module.value}</div>
                <div className="mt-2 text-base font-semibold">{module.title}</div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{module.description}</p>
              </button>
            )
          })}
        </div>
      </div>
    </>
  )
}
