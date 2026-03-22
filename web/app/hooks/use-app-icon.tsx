import { useEffect, useCallback } from 'react'

interface UseAppIconOptions {
  enable?: boolean
  type?: 'icon' | 'emoji' | 'image'
  icon?: string | React.ReactElement
  size?: number
  color?: string
  bgColor?: string
  iconUrl?: string
}

interface IconLinkElement extends HTMLLinkElement {
  rel: string
  type: string
  href: string
}

export function useAppIcon(options: UseAppIconOptions) {
  const {
    enable = true,
    type = 'emoji',
    icon,
    size = 24,
    color = '',
    bgColor = '',
    iconUrl,
  } = options

  const generateSvgIcon = useCallback(async (iconContent: string | React.ReactElement, background: string) => {
    let content = '🤖'
    
    if (typeof iconContent === 'string') {
      if (type === 'emoji') {
        content = type as string
      } else {
        content = iconContent
      }
    }

    return `data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22>`
      + `<rect width=%22100%25%22 height=%22100%25%22 fill=%22${encodeURIComponent(background)}%22 rx=%2230%22 ry=%2230%22 />`
      + `<text x=%2212.5%22 y=%221em%22 font-size=%2275%22 fill=%22${encodeURIComponent(color)}%22>${content}</text>`
      + '</svg>'
  }, [type, color])

  const loadIcon = useCallback(async () => {
    if (!enable) return

    const isValidImageIcon = type === 'image' && iconUrl
    const isValidEmojiIcon = type === 'emoji' && icon
    const isValidIcon = type === 'icon' && icon

    if (!isValidImageIcon && !isValidEmojiIcon && !isValidIcon) return

    try {
      const link: IconLinkElement = document.querySelector('link[rel*="icon"]') || document.createElement('link')
      link.rel = 'shortcut icon'
      link.type = 'image/svg'

      if (isValidImageIcon) {
        link.href = iconUrl
      } else {
        link.href = await generateSvgIcon(icon || '🤖', bgColor || '#000000')
      }

      document.getElementsByTagName('head')[0].appendChild(link)
    } catch (error) {
      console.error('Failed to load app icon:', error)
    }
  }, [enable, type, icon, iconUrl, bgColor, generateSvgIcon])

  useEffect(() => {
    loadIcon()

    // Cleanup function to remove the icon when component unmounts
    return () => {
      const link = document.querySelector('link[rel*="icon"]')
      if (link) {
        link.remove()
      }
    }
  }, [loadIcon])
}
