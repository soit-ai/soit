import * as React from 'react'
import { useCallback, useEffect, useState } from 'react'
import { Search, Bell, HelpCircle, Key, Settings, ExternalLink, BookOpen, MessageSquare, Info, AlertTriangle, Globe, Check, CheckCircle2, GitBranch as Github } from 'lucide-react'
import { ModeSwitcher } from '@/components/common/mode-switcher'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { NavUser } from '@/components/common/nav-user'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useTranslation } from '@/i18n'
import { languages } from '@/i18n/language'
import { setLocaleOnClient } from '@/i18n'
import { toast } from '@/components/ui/sonner'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { useNavigate } from '@/hooks/use-navigate'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'
import {
  getNotificationUnreadCount,
  listNotifications,
  markNotificationRead,
  markNotificationsRead,
  type Notification,
} from '@/services/notification-service'
import { useUserStore } from '@/stores/user'

// Notification item component.
const NotificationItem = ({
  notification,
  onOpen,
}: {
  notification: Notification
  onOpen: (notification: Notification) => void
}) => {
  const icons = {
    info: <Info className="h-4 w-4 text-primary" />,
    warning: <AlertTriangle className="h-4 w-4 text-warning-foreground" />,
    error: <AlertTriangle className="h-4 w-4 text-danger-foreground" />,
    success: <CheckCircle2 className="h-4 w-4 text-success-foreground" />,
  }
  const icon = icons[notification.severity as keyof typeof icons] ?? icons.info
  const timeLabel = notification.created_at
    ? formatDateTime(isoToZonedDate(notification.created_at), 'yyyy-MM-dd HH:mm')
    : ''

  return (
    <div className={cn(
      "flex items-start gap-3 p-3 hover:bg-muted/50 rounded-md cursor-pointer",
      notification.status === 'unread' && "bg-muted/30"
    )}
    onClick={() => onOpen(notification)}
    >
      <div className="mt-1">{icon}</div>
      <div className="flex-1">
        <div className="flex justify-between items-start">
          <div className="font-medium">{notification.title}</div>
          <div className="text-xs text-muted-foreground">{timeLabel}</div>
        </div>
        {notification.content && (
          <p className="text-sm text-muted-foreground mt-1">{notification.content}</p>
        )}
      </div>
    </div>
  )
}

export const RootHeader = () => {
  const navigate = useNavigate()
  const user = useUserStore((state) => state.navUser)
  const [searchQuery, setSearchQuery] = useState('')
  const { t, i18n } = useTranslation()
  const [isChanging, setIsChanging] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)

  const loadUnreadCount = useCallback(async () => {
    try {
      const response = await getNotificationUnreadCount()
      setUnreadCount(response.count || 0)
    } catch (error) {
      console.warn('Failed to load unread notification count:', error)
    }
  }, [])

  const loadNotifications = useCallback(async () => {
    setLoadingNotifications(true)
    try {
      const response = await listNotifications({ page_size: 5 })
      const items = response.items || []
      setNotifications(items)
    } catch (error) {
      console.warn('Failed to load notifications:', error)
      setNotifications([])
    } finally {
      setLoadingNotifications(false)
    }
  }, [])

  useEffect(() => {
    loadUnreadCount()
  }, [loadUnreadCount])

  useEffect(() => {
    if (notificationsOpen) {
      loadNotifications()
    }
  }, [loadNotifications, notificationsOpen])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`)
    }
  }

  // Handle language switch.
  const handleLanguageChange = async (lang: string) => {
    try {
      setIsChanging(true)
      await setLocaleOnClient(lang as any)
      toast.success(t('system.settings.lang.saveSuccess'), {
        description: t('system.settings.lang.settingsApplied'),
      })
    } catch (error) {
      console.warn('Failed to switch language:', error)
      toast.error(t('system.settings.lang.saveError'), {
        description: t('system.settings.lang.settingsError'),
      })
    } finally {
      setIsChanging(false)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await markNotificationsRead({ all: true })
      setNotifications((prev) => prev.map((item) => ({ ...item, status: 'read' })))
      setUnreadCount(0)
    } catch (error) {
      console.warn('Failed to mark notifications as read:', error)
    }
  }

  const handleNotificationOpen = async (notification: Notification) => {
    try {
      if (notification.status === 'unread') {
        await markNotificationRead(notification.id)
        setNotifications((prev) =>
          prev.map((item) => (item.id === notification.id ? { ...item, status: 'read' } : item))
        )
        setUnreadCount((prev) => Math.max(0, prev - 1))
      }
    } catch (error) {
      console.warn('Failed to mark notification as read:', error)
    }
    const action = notification.action || {}
    if (action.deeplink) {
      window.open(action.deeplink, '_blank', 'noopener,noreferrer')
      return
    }
    if (action.route) {
      navigate(action.route)
    }
  }

  return (
    <header className="fixed top-0 z-40 flex h-[var(--root-header-height)] w-[calc(100%-var(--root-sidebar-width)+1px)] shrink-0 items-center gap-3 border-b border-border/60 bg-shell/72 px-5 backdrop-blur-xl">
      <div className="flex flex-row items-center">
        {/* <SidebarTrigger className="-ml-1 text-foreground/80" /> */}
        {/* <Separator orientation="vertical" className="mx-3 h-5 bg-border/70" /> */}
        <div className="text-sm font-semibold uppercase tracking-[0.22em] text-foreground/255">{t('common.app.name')}</div>
        <a
          href="https://github.com/soit-ai/soit"
          target="_blank"
          rel="noopener noreferrer"
          className="ml-3 flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors"
          aria-label={t('layout.header.githubLabel')}
        >
          <div className="hidden sm:flex items-center">
            <div className="flex items-center rounded-full border border-border/70 bg-panel/78 px-2.5 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground shadow-[0_8px_18px_rgba(15,23,42,0.06)]">
              <Github className="mr-1.5 h-3.5 w-3.5" />
              Repo
            </div>
          </div>
        </a>
      </div>

      {/* Search bar */}
      <div className="mx-auto flex max-w-xl flex-1 justify-center">
        <form onSubmit={handleSearch} className="w-full relative">
          <Input
            type="search"
            placeholder={t('layout.header.searchPlaceholder')}
            className="h-10 w-full rounded-[var(--radius-sm)] border-border/70 bg-panel/84 pl-10"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        </form>
      </div>

      <div className="flex items-center justify-end gap-1.5">
        {/* API key management */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="relative border-transparent" aria-label={t('layout.header.apiKey.label')}>
              <Key className="h-5 w-5" />
            </Button>} />
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>{t('layout.header.apiKey.title')}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <Key className="mr-2 h-4 w-4" />
              <span>{t('layout.header.apiKey.view')}</span>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <ExternalLink className="mr-2 h-4 w-4" />
              <span>{t('layout.header.apiKey.docs')}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Notifications */}
        <Popover open={notificationsOpen} onOpenChange={setNotificationsOpen}>
          <PopoverTrigger render={<Button variant="ghost" size="icon" className="relative border-transparent" aria-label={t('layout.header.notifications.label')}>
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <Badge
                  variant="destructive"
                  className="absolute -top-1 -right-1 h-4 min-w-4 p-0 flex items-center justify-center text-[10px]"
                >
                  {unreadCount}
                </Badge>
              )}
            </Button>} />
          <PopoverContent align="end" className="w-80 rounded-[var(--radius-xl)] border-border/70 bg-elevated p-0 backdrop-blur-xl">
            <div className="border-b border-border/70 p-3">
              <div className="flex justify-between items-center">
                <h4 className="font-semibold">{t('layout.header.notifications.title')}</h4>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 text-sm font-normal"
                  onClick={handleMarkAllRead}
                >
                  {t('layout.header.notifications.markAllRead')}
                </Button>
              </div>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              {loadingNotifications ? (
                <div className="p-6 text-center text-muted-foreground">
                  {t('layout.header.notifications.loading')}
                </div>
              ) : notifications.length > 0 ? (
                <div className="p-2">
                  {notifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      onOpen={handleNotificationOpen}
                    />
                  ))}
                </div>
              ) : (
                <div className="p-6 text-center text-muted-foreground">
                  {t('layout.header.notifications.empty')}
                </div>
              )}
            </div>
            <div className="border-t border-border/70 p-2">
              <Button variant="ghost" size="sm" className="w-full justify-center" onClick={() => navigate('/notifications')}>
                {t('layout.header.notifications.viewAll')}
              </Button>
            </div>
          </PopoverContent>
        </Popover>

        {/* Help center */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="border-transparent" aria-label={t('layout.header.help.label')}>
              <HelpCircle className="h-5 w-5" />
            </Button>} />
          <DropdownMenuContent align="end" className="w-56 rounded-[var(--radius-lg)] border-border/70 bg-elevated backdrop-blur-xl">
            <DropdownMenuLabel>{t('layout.header.help.title')}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <BookOpen className="mr-2 h-4 w-4" />
              <span>{t('layout.header.help.docs')}</span>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <MessageSquare className="mr-2 h-4 w-4" />
              <span>{t('layout.header.help.contact')}</span>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Info className="mr-2 h-4 w-4" />
              <span>{t('layout.header.help.about')}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Language switch */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="border-transparent" aria-label={t('layout.header.language.label')} disabled={isChanging}>
              <Globe className="h-5 w-5" />
            </Button>} />
          <DropdownMenuContent align="end" className="w-56 rounded-[var(--radius-lg)] border-border/70 bg-elevated backdrop-blur-xl">
            <DropdownMenuLabel>{t('system.settings.lang.languageSettings')}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {languages.map((lang) => (
              <DropdownMenuItem
                key={lang.value}
                onClick={() => handleLanguageChange(lang.value)}
                className={cn(
                  "flex items-center justify-between",
                  i18n.language === lang.value && "bg-accent"
                )}
                disabled={isChanging}
              >
                <span>{lang.name}</span>
                {i18n.language === lang.value && (
                  <Check className="h-4 w-4 text-primary" />
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Settings */}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="border-transparent" aria-label={t('layout.header.settings.label')} onClick={() => navigate('/settings')}>
              <Settings className="h-5 w-5" />
            </Button>} />
        </DropdownMenu>

        <ModeSwitcher />

        <Separator orientation="vertical" className="mx-2 h-6 bg-border/70" />

        <NavUser user={user} right={true}  />
      </div>
    </header>
  )
}
