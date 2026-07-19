import * as React from 'react'
import { Send, BookOpen, Bot, Frame, Map, PieChart, Settings2, SquareTerminal, LifeBuoy, SquareArrowOutUpRight, Plus, Sparkles, Pencil, Trash2 } from 'lucide-react'
import { NavMain } from '@/components/nav/nav-main'
import { NavProjects } from '@/components/nav/nav-projects'
import { SidebarOptInForm } from '@/components/common/sidebar-opt-in-form'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate, useWindowOpen } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useCallback, useEffect, useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { BoxHeader } from '@/components/ui/app/box-card'
import { Label } from '@/components/ui/label'
import { deleteThread, listThreads, type Thread as RuntimeThread, updateThread } from '@/services/thread-service'
import { useQuery } from '@/hooks/use-query'
import { useMitt } from '@/hooks/use-mitt'
import { useTranslation } from '@/i18n'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { getDateGroupTitle } from '@/utils/date-time'
import useTimestamp from '@/hooks/use-timestamp'
import { toast } from 'sonner'

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

// Extend the Conversation type from service with required fields
interface Conversation extends Omit<RuntimeThread, 'created_at' | 'updated_at'> {
  created_at: string
  updated_at: string
  default_model_ref?: string | null
}

interface GroupedConversations {
  title: string
  conversations: Conversation[]
}

// Default page size for all conversations
const PAGE_SIZE = 100

type BoxSidebarProps = {
  agentId: string
  id: string
  title: string
  setTitle: (title: string) => void
  onNewChat?: () => Promise<void> | void
  providers?: Array<{ id: string; name: string }>
  selectedProvider?: string
  onProviderChange?: (providerId: string) => void
  modelProviderMap?: Map<string, string>
}

export function BoxSidebar({
  agentId,
  id,
  title,
  setTitle,
  onNewChat,
  providers = [],
  selectedProvider,
  onProviderChange,
  modelProviderMap,
  ...props
}: React.ComponentProps<typeof Sidebar> & BoxSidebarProps) {
  const { t } = useTranslation()
  const { formatDate, toZonedDate } = useTimestamp()
  const [pageToken, setPageToken] = useState<string | undefined>(undefined)
  const [nextPageToken, setNextPageToken] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const [allConversations, setAllConversations] = useState<Conversation[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'archived'>('active')
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [conversationToRename, setConversationToRename] = useState<string | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<Conversation | null>(null)
  const [deleting, setDeleting] = useState(false)
  const windowOpen = useWindowOpen()
  const navigate = useNavigate()
  const { emit, useSubcribe } = useMitt()
  const resetConversationList = useCallback(() => {
    setAllConversations([])
    setPageToken(undefined)
    setNextPageToken(null)
    setHasMore(true)
  }, [])

  const {
    data: conversations,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['chat-conversations', pageToken, agentId, statusFilter, searchQuery.trim()],
    queryFn: () =>
      listThreads({
        page_token: pageToken,
        page_size: PAGE_SIZE,
        status: statusFilter === 'all' ? undefined : statusFilter,
        agent_id: agentId === 'default' ? undefined : agentId,
        search: searchQuery.trim() || undefined,
      }),
    options: {
      retry: false,
    },
  })

  useEffect(() => {
    resetConversationList()
  }, [agentId, resetConversationList])

  useEffect(() => {
    if (conversations) {
      const response = conversations as import('@/services/thread-service').PaginatedResponse<RuntimeThread>
      setNextPageToken(response.next_page_token || null)
      setHasMore(Boolean(response.next_page_token))
      const formattedItems = response.items
        .map((item) => {
        let created_at = item.created_at || item.updated_at || new Date().toISOString()
        let updated_at = item.updated_at || item.created_at || created_at
        try {
          if (item.created_at && typeof item.created_at === 'string') {
            created_at = item.created_at
          }
          if (item.updated_at && typeof item.updated_at === 'string') {
            updated_at = item.updated_at
          }
        } catch (error) {
          console.error('Error converting thread time:', error)
          created_at = new Date().toISOString()
          updated_at = created_at
        }

        return {
          ...item,
          created_at,
          updated_at,
          default_model_ref: item.default_model_ref,
        }
      })

      if (!pageToken) {
        setAllConversations(formattedItems)
      } else {
        setAllConversations((prev) => [...prev, ...formattedItems])
      }
    }
  }, [conversations, pageToken])

  const filteredConversations = useMemo(() => {
    const scopedConversations =
      agentId === 'default'
        ? allConversations
        : allConversations.filter(
            (conversation) => conversation.agent_id === agentId
          )

    if (!selectedProvider || !modelProviderMap?.size) {
      return scopedConversations
    }
    return scopedConversations.filter((conversation) => {
      if (!conversation.default_model_ref) {
        return false
      }
      return modelProviderMap.get(conversation.default_model_ref) === selectedProvider
    })
  }, [agentId, allConversations, modelProviderMap, selectedProvider])

  const searchedConversations = useMemo(() => {
    return filteredConversations
  }, [filteredConversations])

  // Group conversations by date
  const groupedConversations = useMemo(() => {
    if (!searchedConversations.length) return []

    const groups: GroupedConversations[] = [
      { title: t('chat.dateGroups.today'), conversations: [] },
      { title: t('chat.dateGroups.yesterday'), conversations: [] },
      { title: t('chat.dateGroups.lastThreeDays'), conversations: [] },
      { title: t('chat.dateGroups.lastWeek'), conversations: [] },
    ]

    const olderGroups: Record<string, Conversation[]> = {}

    searchedConversations.forEach((conversation) => {
      let createdDate: Date
      try {
        createdDate = toZonedDate(conversation.created_at)
      } catch (error) {
        console.error('Error parsing created_at:', error)
        createdDate = new Date()
      }

      const groupTitle = getDateGroupTitle(createdDate)
      const existingGroup = groups.find(g => g.title === groupTitle)
      
      if (existingGroup) {
        existingGroup.conversations.push(conversation)
      } else {
        // Group by month and day
        const monthDay = formatDate(createdDate.toISOString(), 'MM-dd')
        if (!olderGroups[monthDay]) {
          olderGroups[monthDay] = []
        }
        olderGroups[monthDay].push(conversation)
      }
    })

    // Add older groups
    Object.entries(olderGroups).forEach(([date, convs]) => {
      if (convs.length > 0) {
        const dateObj = toZonedDate(convs[0].created_at)
        groups.push({
          title: formatDate(dateObj.toISOString(), 'yyyy-MM-dd'),
          conversations: convs,
        })
      }
    })

    // Filter out empty groups
    return groups.filter((group) => group.conversations.length > 0)
  }, [searchedConversations, t, formatDate, toZonedDate])

  useSubcribe('refresh_chat_sidebar', () => {
    resetConversationList()
    if (!pageToken) {
      refetch()
    }
  })

  const openApp = () => {
    return () => {
      windowOpen('/app', '_blank')
    }
  }

  const handleNewChat = async () => {
    try {
      setTitle(t('chat.sidebar.defaultTitle'))
      await onNewChat?.()
      // Navigate to an empty conversation.
      navigate(`/chat/${agentId}`)
    } catch (error) {
      console.error('Failed to create new conversation:', error)
    }
  }

  const handleLoadMore = () => {
    if (!nextPageToken) return
    setPageToken(nextPageToken)
  }

  const handleRename = async (id: string): Promise<void> => {
    const conversation = allConversations.find((conv) => conv.id === id)
    if (conversation) {
      setNewTitle(conversation.title || '')
    }
    setConversationToRename(conversation?.id || null)
    setIsRenameDialogOpen(true)
  }

  const handleRenameSubmit = async () => {
    if (!conversationToRename || !newTitle.trim()) {
      return
    }
    try {
      setRenaming(true)
      const updated = await updateThread(conversationToRename, {
        title: newTitle.trim(),
      })
      setAllConversations((prev) =>
        prev.map((conversation) =>
          conversation.id === updated.id
            ? { ...conversation, title: updated.title || conversation.title, status: updated.status }
            : conversation
        )
      )
      const renamedThread = allConversations.find((conversation) => conversation.id === updated.id)
      if (renamedThread?.id === id && updated.title) {
        setTitle(updated.title)
      }
      setPageToken(undefined)
      if (!pageToken) {
        await refetch()
      }
      setIsRenameDialogOpen(false)
      setNewTitle('')
      setConversationToRename(null)
    } catch (error) {
      toast.error(t('chat.sidebar.toast.renameError'))
      console.error('Failed to rename conversation:', error)
    } finally {
      setRenaming(false)
    }
  }

  const handleDelete = async (id: string): Promise<void> => {
    const target = allConversations.find((conv) => conv.id === id) || null
    setConversationToDelete(target)
    setIsDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async (): Promise<void> => {
    if (!conversationToDelete) {
      return
    }
    try {
      setDeleting(true)
      await deleteThread(conversationToDelete.id)
      const remainingConversations = allConversations.filter(
        (conversation) => conversation.id !== conversationToDelete.id
      )
      setAllConversations(remainingConversations)
      if (id === conversationToDelete.id) {
        const nextConversation = remainingConversations[0]
        if (nextConversation) {
          setTitle(nextConversation.title || t('chat.sidebar.untitled'))
          navigate(`/chat/${agentId}/${nextConversation.id}`)
        } else {
          setTitle(t('chat.header.defaultTitle'))
          navigate(`/chat/${agentId}`)
        }
      }
      setPageToken(undefined)
      if (!pageToken) {
        await refetch()
      }
      emit('refresh_chat_sidebar')
      setIsDeleteDialogOpen(false)
      setConversationToDelete(null)
      toast.success(t('chat.sidebar.toast.deleteSuccess'))
    } catch (error) {
      toast.error(t('chat.sidebar.toast.deleteError'))
      console.error('Failed to delete conversation history:', error)
    } finally {
      setDeleting(false)
    }
  }

  const handleArchive = async (conversation: Conversation) => {
    await updateThread(conversation.id, { status: 'archived' })
    resetConversationList()
    if (!pageToken) {
      await refetch()
    }
  }

  const handleUnarchive = async (conversation: Conversation) => {
    await updateThread(conversation.id, { status: 'active' })
    resetConversationList()
    if (!pageToken) {
      await refetch()
    }
  }

  // Add effect to update title when id changes
  useEffect(() => {
    if (id && allConversations.length > 0) {
      const currentConversation = allConversations.find((conv) => conv.id === id)
      if (currentConversation && currentConversation.title) {
        setTitle(currentConversation.title)
      }
    }
  }, [id, allConversations, newTitle, setTitle])

  return (
    <>
      <Sidebar className="hidden flex-1 md:flex" {...props}>
        <SidebarHeader className="mt-2">
          <div className="flex flex-1 h-full w-full items-center justify-between px-2">
            <BoxHeader title={t('common.app.name')} subtitle={'Soit'} icon={<Sparkles />} iconType={'icon'} />
            {/* <Label className="flex items-center gap-2 text-sm">
                <span>Unreads</span>
              </Label> */}
            <SquareArrowOutUpRight className="mt-1.5 self-start size-4 cursor-pointer" onClick={openApp()} />
          </div>
          {providers.length > 0 && (
            <div className="mt-3 px-2">
              <Select value={selectedProvider || ''} onValueChange={onProviderChange}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder={t('common.model.selector.labels.provider')} />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.id} value={provider.id}>
                      {provider.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button className="w-auto mt-4 ml-2 mr-2  bg-sidebar-primary text-sidebar-primary-foreground shadow-none" size="sm" onClick={handleNewChat}>
            <Plus /> {t('chat.sidebar.newChat')}
          </Button>
          <div className="px-2">
            <Select
              value={statusFilter}
              onValueChange={(value) => {
                resetConversationList()
                setStatusFilter(value as 'all' | 'active' | 'archived')
              }}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder={t('chat.sidebar.filter.label')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('chat.sidebar.filter.all')}</SelectItem>
                <SelectItem value="active">{t('chat.sidebar.filter.active')}</SelectItem>
                <SelectItem value="archived">{t('chat.sidebar.filter.archived')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <SidebarInput
            className="ml-2 mr-2 w-auto"
            placeholder={t('chat.sidebar.search')}
            value={searchQuery}
            onChange={(event) => {
              resetConversationList()
              setSearchQuery(event.target.value)
            }}
          />
        </SidebarHeader>
        <SidebarContent>
          <ScrollArea className="h-full">
            {isLoading && !pageToken ? (
              <div className="flex items-center justify-center p-2">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 dark:border-gray-200 border-gray-900"></div>
              </div>
            ) : searchedConversations.length > 0 ? (
              <>
                {groupedConversations.map((group, index) => (
                  <NavProjects
                    key={`group-${index}`}
                    title={group.title}
                    projects={group.conversations.map((conv: Conversation) => {
                      const createdDate = toZonedDate(conv.created_at)
                      
                        return {
                          id: conv.id,
                          name: conv.title || t('chat.sidebar.untitled'),
                        url: `/chat/${agentId}/${conv.id}`,
                          icon: Bot,
                          time: formatDate(createdDate.toISOString(), 'HH:mm'),
                          isActive: conv.id === id,
                        moreActions: [
                          {
                            icon: Pencil,
                            label: t('chat.dateGroups.rename'),
                            onClick: () => handleRename(conv.id),
                          },
                          conv.status === 'archived'
                            ? {
                                icon: Sparkles,
                                label: t('chat.dateGroups.unarchive'),
                                onClick: () => handleUnarchive(conv),
                              }
                            : {
                                icon: Sparkles,
                                label: t('chat.dateGroups.archive'),
                                onClick: () => handleArchive(conv),
                              },
                          {
                            icon: Trash2,
                            label: t('chat.dateGroups.delete'),
                            onClick: () => handleDelete(conv.id),
                          },
                        ],
                      }
                    })}
                  />
                ))}
                {hasMore && (
                  <div className="flex justify-center p-2">
                    <Button variant="ghost" size="sm" onClick={handleLoadMore} disabled={isLoading}>
                      {isLoading ? t('chat.dateGroups.loading') : t('chat.dateGroups.loadMore')}
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <div className="p-2 text-center text-sm text-muted-foreground">{t('chat.sidebar.noConversations')}</div>
            )}
          </ScrollArea>
        </SidebarContent>
        <SidebarFooter>
          <div className="p-2">
            <SidebarOptInForm />
          </div>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <Dialog open={isRenameDialogOpen} onOpenChange={setIsRenameDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.operation.rename')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t('common.placeholder.input')}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRenameDialogOpen(false)} disabled={renaming}>
              {t('common.operation.cancel')}
            </Button>
            <Button onClick={handleRenameSubmit} disabled={renaming || !newTitle.trim()}>
              {t('common.operation.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('chat.sidebar.deleteConfirmTitle')}</DialogTitle>
          </DialogHeader>
          <div className="py-2 text-sm text-muted-foreground">
            {t('chat.sidebar.deleteConfirmDescription', {
              name: conversationToDelete?.title || t('chat.sidebar.untitled'),
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)} disabled={deleting}>
              {t('common.operation.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm} disabled={deleting}>
              {t('common.operation.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
