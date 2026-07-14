import * as React from 'react'
import { AudioWaveform, Bot, BrainCog, Command, GalleryVerticalEnd, Workflow, ScrollText, MessageCircleMore, Activity, Settings, Send, Unplug } from 'lucide-react'

import { NavUser } from '@/components/common/nav-user'
import { TeamSwitcher } from '@/components/common/team-switcher'
import { NavSecondary } from '@/components/nav/nav-secondary'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarGroup,
  SidebarGroupContent,
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
  navPrimary: [
    {
      title: 'Chat',
      url: '/chat',
      type: 'chat',
      icon: MessageCircleMore,
      isActive: true,
      isNav: true,
    },
    {
      title: 'Agents',
      url: '/agents',
      type: 'agents',
      icon: Bot,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Workflow',
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
      title: 'Plugins',
      url: '/plugins',
      type: 'plugins',
      icon: Unplug,
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
      title: 'Observe',
      url: '/observe',
      type: 'observe',
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
  ],
  navSecondary: [
    {
      title: 'Feedback',
      url: '/observe/feedback',
      icon: Send,
    },
    // {
    //   title: 'Monitor',
    //   url: '/observe/monitor',
    //   icon: Activity,
    // },
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
      <SidebarHeader >
        <div className="rounded-[var(--radius-lg)] border border-sidebar-border/80 bg-panel/82 px-0 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.06)]">
          <TeamSwitcher teams={data.teams} />
        </div>
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
      <SidebarContent className="overflow-x-hidden px-0 pb-3">
        <ScrollArea className='w-full h-full'>
          <ScrollBar orientation="vertical" />
          <div className="w-full">
            <SidebarGroup className="mt-4">
              <SidebarGroupContent className="px-0">
                <SidebarMenu className="items-center">
                  {data.navPrimary.map((item) => (
                    <SidebarMenuItem key={item.title} className="mt-1 flex justify-center">
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
                        className="mx-auto size-10 cursor-pointer justify-center p-0"
                      >
                        {/* <Link to={item.url} className="flex items-center gap-2"> */}
                        <item.icon className="size-[18px]" />
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
        <NavSecondary items={data.navSecondary||[]} className="mt-auto px-1" />
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/70 px-3 py-3 ">
        <NavUser user={user} />
      </SidebarFooter>
    </div>
  )
}
