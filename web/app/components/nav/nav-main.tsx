'use client'

import { ChevronRight, type LucideIcon } from 'lucide-react'
import { Link } from '@/components/ui/link'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuAction, SidebarMenuButton, SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'

export function NavMain({
  title,
  items,
  activeItem,
}: {
  title?: string
  items: {
    title: string
    url: string
    icon: LucideIcon
    isActive?: boolean
    onClick?: () => void
    items?: {
      title: string
      url: string
      onClick?: () => void
    }[]
  }[]
  activeItem?: {
    title?: string
    url?: string
    type?: string
    icon?: LucideIcon
    isActive?: boolean
  }
}) {
  const navigate = useNavigate()
  return (
    <SidebarGroup>
      {title ? <SidebarGroupLabel>{title}</SidebarGroupLabel> : null}
      <SidebarMenu>
        {items.map((item) => (
          <Collapsible
            key={item.title}
            defaultOpen={item.isActive}
            render={<SidebarMenuItem />}
            className="group/collapsible"
          >
              <CollapsibleTrigger render={<SidebarMenuButton tooltip={item.title} />}>
                <Link
                  to={item.url}
                  onClick={(e) => {
                    if (item.onClick) {
                      e.preventDefault()
                      item.onClick?.()
                    }
                  }}
                  className="flex items-center w-full gap-2 overflow-hidden"
                >
                  <item.icon size={16} />
                  <span className="text-sm">{item.title}</span>
                </Link>
                {item.items && <ChevronRight className="ml-auto transition-transform duration-200 group-data-open/collapsible:rotate-90" />}
              </CollapsibleTrigger>
              {item.items && <CollapsibleContent>
                <SidebarMenuSub>
                  {item.items?.map((subItem) => (
                    <SidebarMenuSubItem key={subItem.title}>
                      <SidebarMenuSubButton render={<a href={subItem.url}>
                          <span>{subItem.title}</span>
                        </a>} />
                    </SidebarMenuSubItem>
                  ))}
                </SidebarMenuSub>
              </CollapsibleContent>}
          </Collapsible>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
