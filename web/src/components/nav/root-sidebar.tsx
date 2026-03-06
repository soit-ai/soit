import * as React from 'react'
import { AudioWaveform, Send, Bot, Command, GalleryVerticalEnd, LifeBuoy, Unplug, ShoppingBag, Workflow, ScrollText, BrainCog, MessageCircleMore, ShieldCheck, Activity, Settings } from 'lucide-react'

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
      title: 'Chat',
      url: '/chat',
      type: 'chat',
      icon: MessageCircleMore,
      isActive: true,
      isNav: true,
    },
    {
      title: 'Bot',
      url: '/bot',
      type: 'bot',
      icon: Bot,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Dataset',
      url: '/dataset',
      type: 'dataset',
      icon: ScrollText,
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
      title: 'Runs',
      url: '/run',
      type: 'run',
      icon: Activity,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Model',
      url: '/model',
      type: 'model',
      icon: BrainCog,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Plugin',
      url: '/plugin',
      type: 'plugin',
      icon: Unplug,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Safe',
      url: '/safe',
      type: 'safe',
      icon: ShieldCheck,
      isActive: false,
      isNav: true,
    },
    {
      title: 'Store',
      url: '/store',
      type: 'store',
      icon: ShoppingBag,
      isActive: false,
      isNav: true,
    },
  ],
  navSecondary: [
    {
      title: 'Feedback',
      url: '/system/feedback',
      icon: Send,
    },
    {
      title: 'Monitor',
      url: '/system/monitor',
      icon: Activity,
    },
    {
      title: 'Setting',
      url: '/setting',
      type: 'setting',
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
    // Match a specific path segment.
    const isMatch = (_path: string) => window.location.pathname.indexOf(_path) > -1
    if (isMatch('/' + type)) {
      return true
    }
    return false
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
        <NavSecondary items={data.navSecondary} className="mt-auto " />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={user} />
      </SidebarFooter>
    </div>
  )
}
