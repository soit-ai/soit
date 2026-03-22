import React, { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '../ui/scroll-area'

interface NavLayoutContextType {
  headerContent: ReactNode
  setHeaderContent: (content: ReactNode) => void
  sidebarContent: ReactNode
  setSidebarContent: (content: ReactNode) => void
}

const NavLayoutContext = createContext<NavLayoutContextType | undefined>(undefined)

export function NavLayoutProvider({ children }: { children: ReactNode }) {
  const [headerContent, setHeaderContent] = React.useState<ReactNode>(null)
  const [sidebarContent, setSidebarContent] = React.useState<ReactNode>(null)

  return (
    <NavLayoutContext.Provider value={{ 
      headerContent, 
      setHeaderContent,
      sidebarContent,
      setSidebarContent
    }}>
      {children}
    </NavLayoutContext.Provider>
  )
}

export function useNavLayout() {
  const context = useContext(NavLayoutContext)
  if (context === undefined) {
    throw new Error('useNavLayout must be used within a NavLayoutProvider')
  }
  return context
} 
export interface NavLayoutProps extends React.HTMLAttributes<HTMLDivElement> {
  left?: React.ReactNode | null | false
  header?: React.ReactNode | null | false
  fixed?: boolean
}

function NavSidebar(props: React.HTMLAttributes<HTMLDivElement>) {
  const { sidebarContent } = useNavLayout()
  const content = props.children || sidebarContent
  if (!content) return null
  const element = content as React.ReactElement<{ className?: string }>
  return React.cloneElement(content as React.ReactElement<{ className?: string }>, {
    className: cn(
      element.props.className,
      'mt-[var(--root-header-height)] pb-[var(--root-header-height)] ml-[calc(var(--root-sidebar-width)+1px)]'
    ),
  })
}

function NavHeader(props: React.HTMLAttributes<HTMLDivElement>) {
  const { headerContent } = useNavLayout()
  const [content, setContent] = useState<ReactNode>(props.children || headerContent)

  useEffect(() => {
    if (headerContent) {
      setContent(headerContent)
    } else {
      setContent(props.children)
    }
  }, [headerContent, props.children])

  if (!content) return null
  const { className, ...rest } = props
  return <header {...rest} className={cn("sticky top-0 z-50 flex w-full shrink-0 items-center gap-2 border-b bg-background p-4", className)} >
    {content}
  </header>
}

export default function NavLayout(props: NavLayoutProps) {
  const { left = null, header = null, children, fixed = false } = props
  return (
    <NavLayoutProvider>
      <div className="flex flex-1 flex-row h-[calc(100vh-var(--root-header-height))]">
        <div className="flex flex-col">
          <NavSidebar>{left}</NavSidebar>
        </div>
        <div className="flex flex-1 flex-col w-full h-full">
          {fixed ? <div className="flex flex-1 flex-col h-full">
            <div className={cn('flex flex-1 flex-col min-h-[calc(100vh-var(--root-header-height)-2px)]', props?.className)}>
              <NavHeader>{header}</NavHeader>
              <div className={cn('flex flex-1 flex-col h-full p-0', props?.className)}>{children}</div>
            </div>
          </div> : <ScrollArea className="flex flex-1 flex-col h-full">
            <NavHeader>{header}</NavHeader>
            <div className={cn('flex flex-1 flex-col h-full p-0', props?.className)}>{children}</div>
          </ScrollArea>}
        </div>
      </div>
    </NavLayoutProvider>
  )
}

export {
  NavLayout,
  NavHeader,
  NavSidebar
}
