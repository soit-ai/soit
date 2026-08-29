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
    tone: 'from-cat-amber/20 via-cat-amber/10 to-transparent',
  },
  {
    key: 'workflow',
    href: '/workflow',
    icon: Sparkles,
    tone: 'from-cat-cyan/20 via-cat-blue/10 to-transparent',
  },
  {
    key: 'tasks',
    href: '/tasks',
    icon: Rocket,
    tone: 'from-cat-red/20 via-cat-red/10 to-transparent',
  },
  {
    key: 'observe',
    href: '/observe',
    icon: Activity,
    tone: 'from-cat-green/20 via-cat-teal/10 to-transparent',
  },
  {
    key: 'settings',
    href: '/settings',
    icon: Settings2,
    tone: 'from-cat-pink/20 via-cat-pink/10 to-transparent',
  },
  {
    key: 'models',
    href: '/models',
    icon: Package2,
    tone: 'from-cat-purple/20 via-cat-indigo/10 to-transparent',
  },
]
