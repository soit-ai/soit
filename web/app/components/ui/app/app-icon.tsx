import { useState, type ReactElement } from 'react'
import { cn } from '@/lib/utils'

export interface AppIconProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: ReactElement | string
  type?: 'icon' | 'emoji' | 'image'
  size?: number
  color?: string
  bgColor?: string
  iconHover?: ReactElement | string
}
// APP application icon generation, can load emoji expressions, can also load pictures
export function AppIcon(props: AppIconProps) {
  const { icon, type = 'icon', size = 24, color = '', bgColor = '', className = '', iconHover } = props

  return (
    <div className={cn('group/appicon flex aspect-square size-12 items-center justify-center rounded-lg  p-1 bg-muted ' + (iconHover ? 'cursor-pointer' : ''), className)}>
      <div className={cn('flex items-center justify-center ' + (iconHover ? 'group-hover/appicon:hidden' : ''))}>
        {type === 'icon' ? icon : null}
        {type === 'image' ? <img src={icon as string} className={`h-${size} w-${size}`} /> : null}
        {type === 'emoji' ? <span className="text-2xl">{icon as string}</span> : null}
      </div>
      {iconHover ? <div className={cn('items-center justify-center hidden ' + (iconHover ? 'group-hover/appicon:flex' : ''))}>{iconHover}</div> : null}
    </div>
  )
}

export default AppIcon
