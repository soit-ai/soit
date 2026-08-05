import { Activity, Bot, Database, Gauge, ShieldCheck, Sparkles, Waypoints } from 'lucide-react'
import { Toaster } from 'sonner'

import { Link } from '@/components/ui/link'
import logoIcon from '@/assets/logo-m.png'

type AuthShellProps = {
  children: React.ReactNode
}

const platformSignals = [
  {
    label: 'Agents',
    value: 'Build',
    description: 'Published capability layer',
    icon: Bot,
    tone: 'border-sky-200/80 bg-sky-50/82 text-sky-700 dark:border-sky-400/20 dark:bg-sky-400/10 dark:text-sky-200',
  },
  {
    label: 'Knowledge',
    value: 'Ground',
    description: 'Retrieval and memory context',
    icon: Database,
    tone: 'border-amber-200/80 bg-amber-50/82 text-amber-700 dark:border-amber-300/20 dark:bg-amber-300/10 dark:text-amber-100',
  },
  {
    label: 'Workflow',
    value: 'Orchestrate',
    description: 'Graph-based execution plans',
    icon: Sparkles,
    tone: 'border-fuchsia-200/80 bg-fuchsia-50/82 text-fuchsia-700 dark:border-fuchsia-300/20 dark:bg-fuchsia-300/10 dark:text-fuchsia-100',
  },
  {
    label: 'Runtime',
    value: 'Observe',
    description: 'Runs, tasks, and feedback loops',
    icon: Activity,
    tone: 'border-emerald-200/80 bg-emerald-50/82 text-emerald-700 dark:border-emerald-300/20 dark:bg-emerald-300/10 dark:text-emerald-100',
  },
]

const railMetrics = [
  { label: 'Governance', value: 'Policy ready' },
  { label: 'Access', value: 'Workspace scoped' },
  { label: 'Telemetry', value: 'Runtime aware' },
]

export function AuthShell({ children }: AuthShellProps) {
  return (
    <>
      <div className="grid min-h-svh bg-[linear-gradient(135deg,#f8fafc_0%,#eef4f8_46%,#edf7f8_100%)] lg:grid-cols-[minmax(460px,0.9fr)_minmax(560px,1.1fr)] dark:bg-[linear-gradient(135deg,#101827_0%,#0f1b2a_52%,#0c2429_100%)]">
      <div className="relative flex min-h-svh flex-col overflow-hidden border-slate-200/70 lg:border-r dark:border-white/10">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(15,23,42,0.035)_1px,transparent_1px),linear-gradient(rgba(15,23,42,0.035)_1px,transparent_1px)] [background-size:36px_36px] dark:bg-[linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(rgba(255,255,255,0.035)_1px,transparent_1px)]" />
        <div className="relative z-10 flex flex-1 flex-col gap-5 p-5 sm:p-7 md:p-9">
          <Link
            to="/"
            className="inline-flex w-fit items-center gap-3 rounded-[0.5rem] border border-transparent px-1 py-1 font-medium text-slate-950 transition-colors hover:border-slate-200/80 hover:bg-white/68 dark:text-white dark:hover:border-white/10 dark:hover:bg-white/5"
          >
            <img src={logoIcon} alt="SOIT logo" className="size-11" />
            <span className="text-xl font-semibold">SOIT AI</span>
          </Link>

          <div className="flex flex-1 items-center justify-center py-3">
            <div className="w-full max-w-[27rem] rounded-[0.5rem] border border-white/80 bg-white/88 px-6 py-7 shadow-[0_24px_80px_rgba(15,23,42,0.11)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/72 dark:shadow-[0_28px_90px_rgba(0,0,0,0.35)] md:px-7 md:py-8">
              {children}
            </div>
          </div>
        </div>
      </div>

      <div className="relative hidden min-h-svh overflow-hidden bg-[linear-gradient(145deg,rgba(231,240,248,0.96)_0%,rgba(244,248,250,0.94)_45%,rgba(224,245,242,0.96)_100%)] lg:block dark:bg-[linear-gradient(145deg,rgba(13,24,39,0.98)_0%,rgba(15,23,42,0.96)_48%,rgba(8,44,49,0.94)_100%)]">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(15,23,42,0.045)_1px,transparent_1px),linear-gradient(rgba(15,23,42,0.045)_1px,transparent_1px)] [background-size:40px_40px] dark:bg-[linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px)]" />
        <div className="absolute inset-x-0 top-0 h-24 bg-[linear-gradient(180deg,rgba(255,255,255,0.62),transparent)] dark:bg-[linear-gradient(180deg,rgba(255,255,255,0.06),transparent)]" />

        <div className="relative z-10 flex h-full min-h-svh flex-col justify-between gap-5 p-7 xl:p-9">
          <div className="max-w-2xl space-y-4 pt-2">
            <div className="inline-flex items-center gap-2 rounded-[0.5rem] border border-slate-200/80 bg-white/70 px-3 py-2 text-xs font-medium text-slate-700 shadow-[0_10px_30px_rgba(15,23,42,0.07)] backdrop-blur dark:border-white/10 dark:bg-white/8 dark:text-slate-200">
              <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
              Enterprise workspace access
            </div>
            <h1 className="max-w-xl text-4xl font-semibold leading-tight text-slate-950 dark:text-white">
              Command your agent workspace from a trusted entry point.
            </h1>
            <p className="max-w-lg text-sm leading-6 text-slate-600 dark:text-slate-300">
              SOIT brings agent building, knowledge grounding, workflow orchestration, and runtime observe into one operational surface.
            </p>
          </div>

          <div className="grid gap-5">
            <div className="rounded-[0.5rem] border border-slate-200/80 bg-white/72 p-4 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/42">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                    Agent Operations Map
                  </div>
                  <div className="mt-1 text-lg font-semibold text-slate-950 dark:text-white">SOIT capability fabric</div>
                </div>
                <div className="inline-flex items-center gap-2 rounded-[0.5rem] border border-emerald-200/80 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 dark:border-emerald-300/20 dark:bg-emerald-300/10 dark:text-emerald-100">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                  </span>
                  Live workspace
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                {platformSignals.map((signal) => {
                  const Icon = signal.icon

                  return (
                    <div key={signal.label} className={`rounded-[0.5rem] border px-4 py-3.5 ${signal.tone}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-[0.18em] opacity-70">{signal.label}</div>
                          <div className="mt-2 text-xl font-semibold text-slate-950 dark:text-white">{signal.value}</div>
                        </div>
                        <div className="rounded-[0.5rem] border border-current/15 bg-white/65 p-2 dark:bg-white/8">
                          <Icon className="h-4 w-4" />
                        </div>
                      </div>
                      <p className="mt-2.5 text-sm leading-5 text-slate-600 dark:text-slate-300">{signal.description}</p>
                    </div>
                  )
                })}
              </div>

              <div className="mt-4 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-3 rounded-[0.5rem] border border-slate-200/70 bg-slate-50/78 px-4 py-3 text-xs font-medium text-slate-600 dark:border-white/10 dark:bg-white/6 dark:text-slate-300">
                <div className="flex items-center gap-2">
                  <Bot className="h-4 w-4 text-sky-600 dark:text-sky-300" />
                  Agent
                </div>
                <Waypoints className="h-4 w-4 text-slate-400" />
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-amber-600 dark:text-amber-200" />
                  Knowledge
                </div>
                <Waypoints className="h-4 w-4 text-slate-400" />
                <div className="flex items-center gap-2">
                  <Gauge className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
                  Runtime
                </div>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              {railMetrics.map((metric) => (
                <div
                  key={metric.label}
                  className="rounded-[0.5rem] border border-slate-200/80 bg-white/66 px-4 py-3 text-sm shadow-[0_14px_34px_rgba(15,23,42,0.07)] backdrop-blur dark:border-white/10 dark:bg-white/7"
                >
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">{metric.label}</div>
                  <div className="mt-2 font-semibold text-slate-950 dark:text-white">{metric.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-slate-200/70 pt-5 text-xs text-slate-500 dark:border-white/10 dark:text-slate-400">
            <span>SOIT</span>
            <span>Agent OS / Knowledge / Workflow / Runtime</span>
          </div>
        </div>
      </div>
      </div>
      <Toaster position="top-right" expand closeButton />
    </>
  )
}
