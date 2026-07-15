import { useEffect, useState, type ComponentType, type ReactElement } from 'react'

export interface ModelIconProps extends React.HTMLAttributes<HTMLDivElement> {
  name?: string
  icon?: string
  className?: string
  size?: number
  type?: 'logo' | 'text'
  shape?: 'circle' | 'square'
}

type ProviderIconComponent = ComponentType<{ size?: number; shape?: 'circle' | 'square'; className?: string }> & {
  Color?: ComponentType<{ size?: number; shape?: 'circle' | 'square'; className?: string }>
  Text?: ComponentType<{ size?: number; shape?: 'circle' | 'square'; className?: string }>
}

type ProviderIconName = 'anthropic' | 'deepseek' | 'gemini' | 'openai'

const providerIconLoaders: Record<ProviderIconName, () => Promise<{ default: ProviderIconComponent }>> = {
  anthropic: () => import('@lobehub/icons/es/Anthropic'),
  deepseek: () => import('@lobehub/icons/es/DeepSeek'),
  gemini: () => import('@lobehub/icons/es/Gemini'),
  openai: () => import('@lobehub/icons/es/OpenAI'),
}

const normalizeProviderIconName = (name: string): ProviderIconName | null => {
  const normalized = name.trim().toLowerCase().replace(/[\s-]+/g, '_')
  if (normalized === 'openai' || normalized === 'openai_compat' || normalized === 'openai_compatible') {
    return 'openai'
  }
  if (normalized === 'deepseek') {
    return 'deepseek'
  }
  if (normalized === 'anthropic' || normalized === 'claude') {
    return 'anthropic'
  }
  if (normalized === 'gemini' || normalized === 'google' || normalized === 'google_ai') {
    return 'gemini'
  }
  return null
}

function FallbackProviderIcon({
  name,
  type,
  className,
  size = 24,
  shape = 'circle',
}: Required<Pick<ModelIconProps, 'name'>> & Pick<ModelIconProps, 'type' | 'className' | 'size' | 'shape'>) {
  const label = name.trim()
  const initials = (label.match(/[a-z0-9]/gi) || []).slice(0, 2).join('').toUpperCase() || '?'

  if (type === 'text') {
    return <span className={className}>{label}</span>
  }

  if (type === 'logo') {
    return (
      <div
        className={className}
        aria-label={label}
        style={{
          alignItems: 'center',
          background: 'hsl(var(--muted))',
          borderRadius: shape === 'square' ? 6 : 999,
          color: 'hsl(var(--muted-foreground))',
          display: 'inline-flex',
          fontSize: Math.max(10, Math.round(size * 0.38)),
          fontWeight: 700,
          height: size,
          justifyContent: 'center',
          lineHeight: 1,
          width: size,
        }}
      >
        {initials}
      </div>
    )
  }

  return <></>
}

// APP application icon generation, can load emoji expressions, can also load pictures
export const ModelIcon = (props: ModelIconProps): ReactElement => {
  const { name, type, className, size, shape } = props
  const [ProviderIcon, setProviderIcon] = useState<ProviderIconComponent | null>(null)
  let _name = name

  useEffect(() => {
    let active = true
    if (!_name || typeof window === 'undefined') {
      setProviderIcon(null)
      return
    }
    const providerIconName = normalizeProviderIconName(_name)
    if (!providerIconName) {
      setProviderIcon(null)
      return
    }
    const loadProviderIcon = providerIconLoaders[providerIconName]

    async function loadIcon() {
      const nextIcon = (await loadProviderIcon()).default
      if (active) {
        setProviderIcon(() => nextIcon)
      }
    }

    loadIcon().catch(() => {
      if (active) {
        setProviderIcon(null)
      }
    })
    return () => {
      active = false
    }
  }, [_name])

  if (!_name) {
    return <></>
  }
  if (!ProviderIcon) {
    return <FallbackProviderIcon name={_name} type={type} className={className} size={size} shape={shape} />
  }
  if (type === 'logo') {
    if (!ProviderIcon.Color) {
      return <ProviderIcon size={size} shape={shape} className={className}></ProviderIcon>
    }
    return <ProviderIcon.Color size={size} shape={shape} className={className}></ProviderIcon.Color>
  }
  if (type === 'text') {
    if (!ProviderIcon.Text) {
      return <></>
    }
    return <ProviderIcon.Text size={size} shape={shape} className={className}></ProviderIcon.Text>
  }
  return <></>
}


export default ModelIcon
