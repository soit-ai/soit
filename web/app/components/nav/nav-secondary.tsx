import * as React from 'react'
import { type LucideIcon } from 'lucide-react'
import { ModeSwitcher } from '@/components/common/mode-switcher'
import { SidebarGroup, SidebarGroupContent, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'

export function NavSecondary({
  items,
  ...props
}: {
  items: {
    title: string
    url: string
    icon: LucideIcon
  }[]
} & React.ComponentPropsWithoutRef<typeof SidebarGroup>) {
  return (
    <SidebarGroup {...props}>
      <SidebarGroupContent>
        <SidebarMenu className="items-center">
          <SidebarMenuItem key={'theme'} className="flex justify-center">
            <SidebarMenuButton size="lg" className="mx-auto size-11 justify-center p-0" render={<ModeSwitcher />} />
          </SidebarMenuItem>
          {items.map((item) => (
            <SidebarMenuItem key={item.title} className="flex justify-center">
              <SidebarMenuButton size="default"
                className="mx-auto size-11 justify-center p-0"
                tooltip={{
                  children: item.title,
                  hidden: false,
                }} render={<a href={item.url}>
                  <item.icon className="size-[18px]" />
                </a>} />
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
