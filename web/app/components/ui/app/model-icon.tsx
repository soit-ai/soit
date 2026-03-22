import { useEffect, useState, type ReactElement } from 'react'
import { cn } from '@/lib/utils'
// import * as ICONS from '@lobehub/icons/es/icons.js'
import { type IconToc, default as toc } from '@lobehub/icons/es/toc.js'
if (typeof window !== 'undefined') {
  // @ts-ignore
  window.ICONS = {}
  import('@lobehub/icons/es/icons.js').then((res) => {
    // @ts-ignore
    window.ICONS = res
  })
}
// import * as ICONS from '@lobehub/icons/es/icons.js'
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
  let _name = name
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
  let ProviderIcon:any = null
  for (const key in toc) {
    const _item = toc[key]
    // console.log(_item.id, toc[key])
    if (_item.id.toLowerCase() === _name.toLowerCase()) {
      // @ts-ignore
      ProviderIcon = window.ICONS[_item.id]
      // console.log(_item.id, ProviderIcon)
      break
    }
  }
  if (!ProviderIcon) {
    // @ts-ignore
    ProviderIcon = window.ICONS[_name]
  }
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
