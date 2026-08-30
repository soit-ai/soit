import { useEffect, useRef, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { IconCheck, IconChevronRight } from '@/console/components/icons'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listMyWorkspaces } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'

interface WorkspaceSwitcherProps {
  workspaceId: string
  /** Falls back to the id while the name is still loading. */
  label: string
  environment?: string | null
}

/**
 * Switch the workspace every request is scoped to.
 *
 * The scope lives in one place — `workspace_id` in storage, sent as a header on
 * every call — so switching is: write the new id, throw away everything read
 * under the old one, and reload. Clearing the whole query cache rather than
 * threading the workspace through every query key is deliberate: a single
 * missed key would show one workspace's rows inside another, and there is no
 * cache entry here worth keeping across a switch anyway.
 */
export function WorkspaceSwitcher({ workspaceId, label, environment }: WorkspaceSwitcherProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const currentUser = useUserStore((state) => state.currentUser)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const workspaces = useQuery({
    queryKey: ['console', 'shell', 'my-workspaces'],
    queryFn: () => listMyWorkspaces({ suppressErrorToast: true }),
    options: { enabled: open, retry: false, refetchOnWindowFocus: false },
  })
  const rows = workspaces.data || []

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const switchTo = (id: string) => {
    setOpen(false)
    if (id === workspaceId) return
    localStorage.setItem('workspace_id', id)
    if (currentUser) setCurrentUser({ ...currentUser, workspace_id: id })
    queryClient.clear()
    // A full reload rather than a route change: every open screen holds data
    // read under the old scope, and re-mounting the tree is the only way to be
    // sure none of it survives.
    window.location.assign('/')
  }

  return (
    <div className="ws-switch" ref={containerRef}>
      <button
        type="button"
        className="ws-switch-trigger"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={t('console.shell.switchWorkspace')}
      >
        <span className="mono block truncate">
          {[label, environment].filter(Boolean).join(' · ')}
        </span>
        <IconChevronRight size={12} />
      </button>
      {open && (
        <div className="ws-switch-menu" role="listbox">
          {rows.length === 0 ? (
            <div className="ws-switch-empty">
              {workspaces.isPending
                ? t('console.common.loading')
                : t('console.shell.noOtherWorkspaces')}
            </div>
          ) : (
            rows.map((row) => (
              <button
                key={row.id}
                type="button"
                role="option"
                aria-selected={row.id === workspaceId}
                className="ws-switch-item"
                onClick={() => switchTo(row.id)}
              >
                <span className="truncate">{row.name}</span>
                <span className="dimmer mono">{row.role}</span>
                {row.id === workspaceId && <IconCheck size={12} />}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
