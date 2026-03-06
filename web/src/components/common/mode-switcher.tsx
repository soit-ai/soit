'use client'

import { MoonIcon, SunIcon } from 'lucide-react'
import { useTheme } from '@/components/theme-provider'

import { Button } from '@/components/ui/button'

export function ModeSwitcher() {
  const { theme, setTheme } = useTheme()
  const toggleTheme = () => {
    console.log('toggleTheme')
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <Button variant="ghost" className="group/toggle h-8 w-8 px-0" onClick={toggleTheme}>
      <SunIcon className="block dark:hidden text-black" />
      <MoonIcon className="hidden dark:block" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}
