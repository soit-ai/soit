import { useTranslation } from '@/i18n'
import { BoxSidebar } from './ui/box-sidebar'
import { NavLayout, NavHeader } from '@/components/layout/nav-layout'
import { RefreshCwIcon, Share2, PlusCircle, MoreHorizontal, InfoIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useParams } from 'react-router'
import { useChat } from '@/hooks/use-chat'
import { useMitt } from '@/hooks/use-mitt'
import { useState, useMemo, useEffect, useCallback } from 'react'
import { useNavigate } from '@/hooks/use-navigate'
import { SelectModel, type ModelProps, type ModelType } from '@/components/ui/form/select-model'
import { toast } from 'sonner'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useQuery } from '@/hooks/use-query'
import { listModels, type ModelLibraryItem } from '@/services/provider-service'
import { getAgent, listAgents, type Agent } from '@/services/agent-service'
import { getThread } from '@/services/thread-service'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  DEFAULT_CHAT_PROVIDER,
  resolveDefaultChatModel,
  resolveStoredChatModel,
  resolveStoredChatProvider,
  isDeepThinkingEnabled,
} from '@/components/ui/chat/defaults'

type ProviderOption = {
  id: string
  name: string
}

function IndexPage() {
  const { emit, useSubcribe } = useMitt()
  const { t } = useTranslation()
  const { agentId = 'default', threadId = '' } = useParams()
  const navigate = useNavigate()
  const [selectedProvider, setSelectedProvider] = useState(() => {
    return resolveStoredChatProvider()
  })
  const [selectedModel, setSelectedModel] = useState(() => {
    return resolveStoredChatModel()
  })
  const { data: activeThread } = useQuery({
    queryKey: ['chat-thread', threadId],
    queryFn: () => getThread(threadId),
    options: {
      enabled: Boolean(threadId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const chat = useChat({
    agentId,
    threadId,
    modelName: selectedModel,
  })

  const { data: modelConfigs = [] } = useQuery<ModelLibraryItem[]>({
    queryKey: ['chat-models'],
    queryFn: () => listModels(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: activeAgent } = useQuery<Agent | null>({
    queryKey: ['agent', agentId],
    queryFn: () => (agentId && agentId !== 'default' ? getAgent(agentId) : Promise.resolve(null)),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: agentPage } = useQuery({
    queryKey: ['chat-agents'],
    queryFn: () => listAgents({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const providers = useMemo<ProviderOption[]>(() => {
    const map = new Map<string, ProviderOption>()
    for (const model of modelConfigs) {
      if (!map.has(model.provider)) {
        map.set(model.provider, {
          id: model.provider,
          name: model.provider,
        })
      }
    }
    return Array.from(map.values())
  }, [modelConfigs])

  const modelProviderMap = useMemo(() => {
    const map = new Map<string, string>()
    modelConfigs.forEach((model) => {
      map.set(model.modelName, model.provider)
    })
    return map
  }, [modelConfigs])

  const chatModels = useMemo<ModelProps[]>(() => {
    return modelConfigs
      .filter((model) => model.isActive && model.modelType === 'llm')
      .map((model) => ({
        id: model.id,
        label: model.name || model.modelName,
        value: model.modelName,
        type: 'chat' as ModelType,
        provider: model.provider,
        contextSize: model.contextLength,
      }))
  }, [modelConfigs])

  const agentOptions = useMemo(() => {
    const items = agentPage?.items || []
    return [
      { id: 'default', label: 'General Chat' },
      ...items.map((agent) => ({
        id: agent.id,
        label: `${agent.name}${agent.published_version_id ? '' : ' · Draft'}`,
      })),
    ]
  }, [agentPage?.items])

  const [title, setTitle] = useState(t('chat.header.defaultTitle'))

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat_default_model', selectedModel)
    }
  }, [selectedModel])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat_default_provider', selectedProvider)
    }
  }, [selectedProvider])

  useEffect(() => {
    if (!chatModels.length) {
      return
    }
    const hasSelected = chatModels.some((model) => model.value === selectedModel)
    if (hasSelected) {
      return
    }

    const preferredDefaultModel = resolveDefaultChatModel(isDeepThinkingEnabled())
    const providerScopedModels = selectedProvider
      ? chatModels.filter((model) => model.provider === selectedProvider)
      : chatModels
    const preferredModel =
      providerScopedModels.find((model) => model.value === preferredDefaultModel) ||
      chatModels.find((model) => model.value === preferredDefaultModel) ||
      providerScopedModels[0] ||
      chatModels[0]
    if (preferredModel) {
      setSelectedModel(preferredModel.value)
    }
  }, [chatModels, selectedModel, selectedProvider])

  useEffect(() => {
    if (!providers.length) {
      return
    }
    const hasProvider = providers.some((provider) => provider.id === selectedProvider)
    if (!selectedProvider || !hasProvider) {
      const preferredProvider =
        providers.find((provider) => provider.id === DEFAULT_CHAT_PROVIDER)?.id ||
        providers[0].id
      setSelectedProvider(preferredProvider)
    }
  }, [providers, selectedProvider])

  useEffect(() => {
    const selected = chatModels.find((model) => model.value === selectedModel)
    if (selected?.provider && selected.provider !== selectedProvider) {
      setSelectedProvider(selected.provider)
    }
  }, [chatModels, selectedModel, selectedProvider])

  useEffect(() => {
    if (!selectedProvider) {
      return
    }
    const providerModels = chatModels.filter((model) => model.provider === selectedProvider)
    if (!providerModels.length) {
      return
    }
    const hasModel = providerModels.some((model) => model.value === selectedModel)
    if (!hasModel) {
      setSelectedModel(providerModels[0].value)
    }
  }, [chatModels, selectedProvider, selectedModel])

  useSubcribe('chat_thread_created', (payload: any) => {
    if (!payload || payload.agentId !== agentId) {
      return
    }
    if (payload.threadId && payload.threadId !== threadId) {
      navigate(`/chat/${agentId}/${payload.threadId}`)
    }
  })

  useSubcribe('chat_completion_finished', (payload: any) => {
    if (!payload || payload.agentId !== agentId) {
      return
    }
    if (payload.threadId && payload.threadId === threadId) {
      chat.refreshHistory()
    }
    emit('refresh_chat_sidebar')
  })

  useEffect(() => {
    if (activeThread?.thread?.title) {
      setTitle(activeThread.thread.title)
    }
  }, [activeThread?.thread?.title])

  const handleRefresh = () => {
    chat.refreshHistory()
    emit('refresh_chat_sidebar')
  }

  const handleNewChat = useCallback(() => {
    navigate(`/chat/${agentId}`)
  }, [agentId, navigate])

  // Share a conversation.
  const handleShareChat = async () => {
    if (typeof window === 'undefined') {
      return
    }
    if (!threadId) {
      toast.info(t('chat.header.shareEmpty'))
      return
    }
    try {
      await navigator.clipboard.writeText(window.location.href)
      toast.success(t('chat.header.shareCopied'))
    } catch (error) {
      console.error('Failed to copy share link:', error)
      toast.error(t('chat.header.shareCopyFailed'))
    }
  }

  const handleTitleChange = (title: string) => {
    setTitle(title)
  }

  const handleAgentChange = (nextAgentId: string) => {
    if (nextAgentId === agentId) {
      return
    }
    navigate(nextAgentId === 'default' ? '/chat' : `/chat/${nextAgentId}`)
  }

  const renderHeader = () => {
    return (
      <div className="flex flex-1 justify-between items-center bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <div className="flex items-center">
            <Button variant="ghost" size="sm" className="gap-2">
              <PlusCircle className="h-4 w-4" />
              <span className="hidden sm:inline">
                {activeAgent?.name ? `${activeAgent.name} · ${title}` : title}
              </span>
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-3 mr-2">
          <div className="flex items-center w-[220px]">
            <Select value={agentId} onValueChange={handleAgentChange}>
              <SelectTrigger>
                <SelectValue placeholder="Select agent" />
              </SelectTrigger>
              <SelectContent>
                {agentOptions.map((agentOption) => (
                  <SelectItem key={agentOption.id} value={agentOption.id}>
                    {agentOption.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Model selector */}
          <div className="flex items-center w-[320px]">
            <SelectModel
              value={selectedModel}
              onChange={(value) => setSelectedModel(value)}
              models={chatModels}
              disabled={!chatModels.length}
            />
          </div>

          {/* Share button */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={handleShareChat}>
                  <Share2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t('chat.header.share')}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* More options */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleRefresh}>
                <RefreshCwIcon className="mr-2 h-4 w-4" />
                {t('chat.header.refresh')}
              </DropdownMenuItem>
              <DropdownMenuItem>
                <InfoIcon className="mr-2 h-4 w-4" />
                {t('chat.header.info')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    )
  }

  return (
    <NavLayout
      left={
        <BoxSidebar
          agentId={agentId}
          id={threadId}
          title={title}
          setTitle={handleTitleChange}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
          modelProviderMap={modelProviderMap}
          onNewChat={handleNewChat}
        ></BoxSidebar>
      }
      fixed={true}
      className="bg-gradient-to-b from-background to-muted/20"
    >
      <NavHeader>{renderHeader()}</NavHeader>
      <div className="flex flex-col h-full w-full">
        <div className="flex-1 overflow-hidden">
          <chat.ChatBox
            key={`${agentId}:${threadId || 'new'}`}
            threadId={threadId || undefined}
            initInputPosition="center"
            className="p-0 h-full"
          />
        </div>
      </div>
    </NavLayout>
  )
}

export default IndexPage
