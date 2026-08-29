import { Folder, MoreHorizontal, Share, Trash2, type LucideIcon } from 'lucide-react'
import { Link } from '@/components/ui/link'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuAction, SidebarMenuButton, SidebarMenuItem, useSidebar } from '@/components/ui/sidebar'

export function NavProjects({
  title,
  projects,
}: {
  title?: string
  projects: {
    id?: string
    name: string
    subname?: any
    url: string
    icon: LucideIcon
    isActive?: boolean
    onClick?: () => void
    moreActions?: {
      icon: LucideIcon
      label: string
      onClick?: () => void
    }[]
  }[]
}) {
  const { isMobile } = useSidebar()

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      {title ? <SidebarGroupLabel>{title}</SidebarGroupLabel> : null}
      <SidebarMenu>
        {projects.map((item) => (
          <SidebarMenuItem key={item.id || item.name}>
            <SidebarMenuButton isActive={item.isActive} render={<Link
                to={item.url}
                onClick={(e) => {
                  if (item.onClick) {
                    e.preventDefault()
                    item.onClick?.()
                  }
                }}
                className="flex items-center gap-2"
              >
                <item.icon size={16} />
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate text-sm">{item.name}</span>
                  {typeof item.subname == 'string' ? <span className="truncate text-[10px]">{item.subname}</span> : item.subname}
                </div>
              </Link>} />
            {item.moreActions && (
              <DropdownMenu>
                <DropdownMenuTrigger render={<SidebarMenuAction showOnHover>
                    <MoreHorizontal />
                    <span className="sr-only">More</span>
                </SidebarMenuAction>} />
              <DropdownMenuContent className="w-48" side={isMobile ? 'bottom' : 'right'} align={isMobile ? 'end' : 'start'}>
                {item.moreActions?.map((more) => (
                  <DropdownMenuItem key={more.label} onClick={more.onClick}>
                    <more.icon className="text-muted-foreground" />
                    <span>{more.label}</span>
                  </DropdownMenuItem>
                ))}
                {/* <DropdownMenuItem>
                  <Share className="text-muted-foreground" />
                  <span>Share Project</span>
                </DropdownMenuItem> */}
                {/* <DropdownMenuSeparator /> */}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </SidebarMenuItem>
        ))}
        {/* <SidebarMenuItem>
          <SidebarMenuButton>
            <MoreHorizontal />
            <span>More</span>
          </SidebarMenuButton>
        </SidebarMenuItem> */}
      </SidebarMenu>
    </SidebarGroup>
  )
}
