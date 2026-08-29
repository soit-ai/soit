import { Link } from 'react-router'

import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'
import logoIcon from '@/assets/logo-m.png'

export function TeamSwitcher() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" className="p-0 h-full w-full flex items-center justify-center" render={<Link to="/" aria-label="SOIT home">
            <div className="text-sidebar-primary-foreground flex size-10 items-center justify-center rounded-lg">
              <img src={logoIcon} alt="SOIT" className="size-12" />
            </div>
          </Link>} />
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
