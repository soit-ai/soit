import {
  Activity,
  Database,
  Package2,
  Rocket,
  Settings2,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'

export type PlatformModuleConfig = {
  key: string
  href: string
  icon: LucideIcon
  tone: string
}

export const platformModules: PlatformModuleConfig[] = [
  {
    key: 'knowledge',
    href: '/knowledge',
    icon: Database,
    tone: 'from-amber-500/20 via-orange-500/10 to-transparent',
  },
  {
    key: 'workflow',
    href: '/workflow',
    icon: Sparkles,
    tone: 'from-cyan-500/20 via-sky-500/10 to-transparent',
  },
  {
    key: 'tasks',
    href: '/tasks',
    icon: Rocket,
    tone: 'from-rose-500/20 via-red-500/10 to-transparent',
  },
  {
    key: 'observability',
    href: '/observability',
    icon: Activity,
    tone: 'from-emerald-500/20 via-teal-500/10 to-transparent',
  },
  {
    key: 'settings',
    href: '/settings',
    icon: Settings2,
    tone: 'from-fuchsia-500/20 via-pink-500/10 to-transparent',
  },
  {
    key: 'models',
    href: '/models',
    icon: Package2,
    tone: 'from-violet-500/20 via-indigo-500/10 to-transparent',
  },
]
