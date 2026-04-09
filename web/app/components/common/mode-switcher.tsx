'use client'

import { MoonIcon, SunIcon } from 'lucide-react'
import { useTheme } from '@/components/theme-provider'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function ModeSwitcher({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()
  const toggleTheme = () => {
    console.log('toggleTheme')
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <Button variant="ghost" className={cn("group/toggle h-8 w-8 px-0", className)} onClick={toggleTheme}>
      <SunIcon className="block dark:hidden text-black" />
      <MoonIcon className="hidden dark:block" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}
