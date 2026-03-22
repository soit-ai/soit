import * as React from 'react'
import { AudioWaveform, Bot, Command, GalleryVerticalEnd, Workflow, ScrollText, BrainCog, MessageCircleMore, Activity, Settings, LayoutDashboard, Send, Unplug } from 'lucide-react'

import { NavUser } from '@/components/common/nav-user'
import { TeamSwitcher } from '@/components/common/team-switcher'
import { NavSecondary } from '@/components/nav/nav-secondary'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarGroup,
  SidebarGroupContent,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'

import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'
import { useUserStore } from '@/stores/user'
// Sample data for the sidebar.
const data = {
  teams: [
    {
      name: 'Acme Inc',
      logo: GalleryVerticalEnd,
      plan: 'Enterprise',
    },
    {
      name: 'Acme Corp.',
      logo: AudioWaveform,
      plan: 'Startup',
    },
    {
      name: 'Evil Corp.',
      logo: Command,
      plan: 'Free',
    },
  ],
  navApp: [
    {
      title: 'Dashboard',
      url: '/',
      type: 'dashboard',
      icon: LayoutDashboard,
      isActive: true,
      isNav: true,
    },
    {
      title: 'Agents',
      url: '/agents',
      type: 'agents',
      icon: Bot,
      isActive: true,
      isNav: true,
    },
    {
      title: 'Chat',
      url: '/chat',
      type: 'chat',
      icon: MessageCircleMore,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Workflows',
      url: '/workflow',
      type: 'workflow',
      icon: Workflow,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Knowledge',
      url: '/knowledge',
      type: 'knowledge',
      icon: ScrollText,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Tasks',
      url: '/tasks',
      type: 'tasks',
      icon: Command,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Observability',
      url: '/observability',
      type: 'observability',
      icon: Activity,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Models',
      url: '/models',
      type: 'models',
      icon: BrainCog,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Plugins',
      url: '/plugins',
      type: 'plugins',
      icon: Unplug,
      isActive: false,
      isNav: true,
    },
  ],
  navSecondary: [
    {
      title: 'Feedback',
      url: '/observability/feedback',
      icon: Send,
    },
    {
      title: 'Monitor',
      url: '/observability/monitor',
      icon: Activity,
    },
    {
      title: 'Settings',
      url: '/settings',
      type: 'settings',
      icon: Settings,
      isActive: false,
      isNav: true,
    },
  ],
}

export function RootSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  // Note: I'm using state to show active item.
  // IRL you should use the url/router.
  const [activeItem, setActiveItem] = React.useState<any>(null)
  const user = useUserStore((state) => state.navUser)
  const { setOpen } = useSidebar()
  const navigate = useNavigate()

  // Check if the current path matches.
  const checkActive = (type?: string) => {
    const pathname = window.location.pathname
    if (type === 'dashboard') {
      return pathname === '/' || pathname.startsWith('/dashboard')
    }
    return pathname.startsWith(`/${type}`)
  }
  return (
    <div className={cn('bg-sidebar', props.className)}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      {/* <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild className="md:h-8 md:p-0">
                <a href="#">
                  <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                    <Command className="size-4" />
                  </div>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">Acme Inc</span>
                    <span className="truncate text-xs">Enterprise</span>
                  </div>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader> */}
      <SidebarContent className="overflow-x-hidden">
        <ScrollArea className='w-[var(--root-sidebar-width)] h-full'>
          <ScrollBar orientation="vertical" />
          <div className="w-[var(--root-sidebar-width)]">
            <SidebarGroup className="mt-8">
              <SidebarGroupContent className="px-0">
                <SidebarMenu>
                  {data.navApp.map((item) => (
                    <SidebarMenuItem key={item.title} className="mt-3">
                      <SidebarMenuButton
                        // size="lg"
                        tooltip={{
                          children: item.title,
                          hidden: false,
                        }}
                        onClick={() => {
                          setActiveItem(item)
                          if (item?.isNav === false) {
                            setOpen(false)
                          } else {
                            setOpen(true)
                          }
                          navigate(item.url)
                        }}
                        isActive={activeItem?.type === item.type || checkActive(item.type)}
                        className="px-2 cursor-pointer"
                      >
                        {/* <Link to={item.url} className="flex items-center gap-2"> */}
                        <item.icon className="size-4" />
                        {/* <span>{item.title}</span> */}
                        {/* </Link> */}
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </div>
        </ScrollArea>
        <NavSecondary items={data.navSecondary||[]} className="mt-auto " />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={user} />
      </SidebarFooter>
    </div>
  )
}
