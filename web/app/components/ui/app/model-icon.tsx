import { useEffect, useState, type ReactElement } from 'react'
import type { IconToc } from '@lobehub/icons/es/types/toc'

type IconRegistry = Record<string, any>
export interface ModelIconProps extends React.HTMLAttributes<HTMLDivElement> {
  name?: string
  icon?: string
  className?: string
  size?: number
  type?: 'logo' | 'text'
  shape?: 'circle' | 'square'
}
// APP application icon generation, can load emoji expressions, can also load pictures
export const ModelIcon = (props: ModelIconProps): ReactElement => {
  const { name, type, className, size, shape } = props  
  const [ProviderIcon, setProviderIcon] = useState<any>(null)
  let _name = name

  useEffect(() => {
    let active = true
    if (!_name || typeof window === 'undefined') {
      setProviderIcon(null)
      return
    }

    async function loadIcon() {
      const [iconsModule, tocModule] = await Promise.all([
        import('@lobehub/icons/es/icons.js'),
        import('@lobehub/icons/es/toc.js'),
      ])
      const icons = iconsModule as IconRegistry
      const toc = tocModule.toc as IconToc[]
      let nextIcon: any = null
      for (const item of toc) {
        if (item.id.toLowerCase() === _name!.toLowerCase()) {
          nextIcon = icons[item.id]
          break
        }
      }
      if (!nextIcon) {
        nextIcon = icons[_name!]
      }
      if (active) {
        setProviderIcon(nextIcon ?? null)
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
  // switch (_name.toLocaleLowerCase()) {
  //   case 'openai':
  //     _name = 'OpenAI'
  //     break
  //   case 'deepseek':
  //     _name = 'DeepSeek'
  //     break
  //   default:
  //     break
  // }
  if (!ProviderIcon) {
    return <></>
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
