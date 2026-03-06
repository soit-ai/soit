import { cn } from '@/lib/utils'
import { AppIcon } from '@/components/ui/app/app-icon'
import { ModelIcon as ModelIconComponent } from '@/components/ui/app/model-icon'
import type { ReactElement } from 'react'
import React from 'react'

// model icon
export function ModelIcon(props: { name?: string; icon?: string; size?: number; className?: string }) {
  const { name = '', icon = '', size = 36, className = '' } = props
  if (icon) {
    return icon
  }
  return (
    <>
      <IconBox name={name} type="logo" size={size} className={cn('', className)} />
    </>
  )
}

// provider icon
export function ProviderIcon(props: { name?: string; icon?: string; size?: number; className?: string }) {
  const { name = '', icon = '', size = 36, className = '' } = props
  if (icon) {
    return icon
  }
  return (
    <>
      <IconBox name={name} type="logo" size={size} className={cn('', className)} />
    </>
  )
}

// provider app icon
export function ProviderAppIcon(props: { name?: string; icon?: string; size?: number; className?: string }) {
  const { name = '', icon = '', size = 36, className = '' } = props
  if (icon) {
    return <AppIcon icon={icon} type={'icon'} className={cn('', className)} />
  }
  return <AppIcon icon={<IconBox name={name} type="logo" size={size} />} type={'icon'} className={cn('', className)} />
}

// provider text icon
export function ProviderTextIcon(props: { name?: string; icon?: string; size?: number; className?: string }) {
  const { name = '', icon = '', size = 24, className = '' } = props
  if (icon) {
    return icon
  }
  return <IconBox name={name} type="text" size={size} className={cn('', className)} />
}

// icon box
export function IconBox(props: { name?: string; icon?: string; className?: string; size?: number; type: 'logo' | 'text'; shape?: 'circle' | 'square' }) {
  const { name = '', icon = '', className = '', size = 36, shape = 'circle', type } = props
  const renderIcon = () => {
    return <ModelIconComponent name={name} type={type} className={cn('', className)} size={size} shape={shape} />
  }
  return <>{renderIcon()}</>
}

