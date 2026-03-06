import { useTranslation } from '@/i18n'
import { useState, useEffect } from 'react'
import { useParams } from 'react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Search, Filter, Calendar } from 'lucide-react'
import { LogHeader, ConversationTable, LogTable, ErrorTable } from '@/pages/bot/detail/ui/log'
import { useNavLayout } from '@/components/layout/nav-layout'

function Page() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState('conversations')
  const [searchQuery, setSearchQuery] = useState('')
  const [timeRange, setTimeRange] = useState('7d')
  const [logType, setLogType] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const { setHeaderContent } = useNavLayout()

  // Set header content.
  useEffect(() => {
    setHeaderContent(<LogHeader onRefresh={loadData} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  // Mock log data.
  const [logs, setLogs] = useState<
    Array<{
      id: string
      timestamp: string
      type: 'info' | 'warning' | 'error'
      message: string
      details: string
      sessionId?: string
    }>
  >([])

  // Mock conversation data.
  const [conversations, setConversations] = useState<
    Array<{
      id: string
      startTime: string
      endTime: string
      user: string
      messageCount: number
      status: 'completed' | 'error' | 'interrupted'
    }>
  >([])

  // Mock error data.
  const [errors, setErrors] = useState<
    Array<{
      id: string
      timestamp: string
      errorCode: string
      message: string
      source: string
      resolved: boolean
    }>
  >([])

  // Load log data.
  useEffect(() => {
    loadData()
  }, [activeTab, timeRange, logType])

  const loadData = () => {
    setIsLoading(true)

    // Simulate API latency.
    setTimeout(() => {
      if (activeTab === 'logs') {
        // Mock log data.
        const mockLogs = [
          {
            id: 'log-1',
            timestamp: '2025-06-01 16:45:23',
            type: 'info' as const,
            message: 'Bot session initialized',
            details: 'User ID: user-123, Session ID: session-456',
          },
          {
            id: 'log-2',
            timestamp: '2025-06-01 16:46:12',
            type: 'info' as const,
            message: 'Knowledge retrieval completed',
            details: 'Query: "Product features", matched documents: 5',
            sessionId: 'session-456',
          },
          {
            id: 'log-3',
            timestamp: '2025-06-01 16:47:05',
            type: 'warning' as const,
            message: 'Model response timeout',
            details: 'Model: gpt-4o, prompt length: 2048 tokens',
            sessionId: 'session-456',
          },
          {
            id: 'log-4',
            timestamp: '2025-06-01 16:48:30',
            type: 'error' as const,
            message: 'API call failed',
            details: 'Error code: 429, reason: rate limit',
            sessionId: 'session-456',
          },
          {
            id: 'log-5',
            timestamp: '2025-06-01 16:50:15',
            type: 'info' as const,
            message: 'Session ended',
            details: 'Duration: 4m 52s, messages: 8',
            sessionId: 'session-456',
          },
        ]
        setLogs(mockLogs)
      } else if (activeTab === 'conversations') {
        // Mock conversation data.
        const mockConversations = [
          {
            id: 'conv-1',
            startTime: '2025-06-01 16:45:23',
            endTime: '2025-06-01 16:50:15',
            user: 'Alex',
            messageCount: 8,
            status: 'completed' as const,
          },
          {
            id: 'conv-2',
            startTime: '2025-06-01 15:30:10',
            endTime: '2025-06-01 15:35:45',
            user: 'Jordan',
            messageCount: 5,
            status: 'completed' as const,
          },
          {
            id: 'conv-3',
            startTime: '2025-06-01 14:20:33',
            endTime: '2025-06-01 14:22:15',
            user: 'Taylor',
            messageCount: 3,
            status: 'error' as const,
          },
          {
            id: 'conv-4',
            startTime: '2025-06-01 12:05:18',
            endTime: '2025-06-01 12:15:42',
            user: 'Morgan',
            messageCount: 12,
            status: 'completed' as const,
          },
          {
            id: 'conv-5',
            startTime: '2025-06-01 10:30:55',
            endTime: '2025-06-01 10:32:20',
            user: 'Casey',
            messageCount: 2,
            status: 'interrupted' as const,
          },
        ]
        setConversations(mockConversations)
      } else if (activeTab === 'errors') {
        // Mock error data.
        const mockErrors = [
          {
            id: 'err-1',
            timestamp: '2025-06-01 16:48:30',
            errorCode: 'API-429',
            message: 'API call failed: rate limit',
            source: 'Model call',
            resolved: false,
          },
          {
            id: 'err-2',
            timestamp: '2025-06-01 14:22:15',
            errorCode: 'API-500',
            message: 'Internal server error',
            source: 'Knowledge retrieval',
            resolved: true,
          },
          {
            id: 'err-3',
            timestamp: '2025-05-31 18:12:40',
            errorCode: 'AUTH-401',
            message: 'Authorization failed: invalid API key',
            source: 'External tool call',
            resolved: true,
          },
          {
            id: 'err-4',
            timestamp: '2025-05-31 09:45:22',
            errorCode: 'TIMEOUT-504',
            message: 'Request timeout: model response timeout',
            source: 'Model call',
            resolved: false,
          },
          {
            id: 'err-5',
            timestamp: '2025-05-30 14:33:10',
            errorCode: 'DATA-400',
            message: 'Invalid request: parameter format error',
            source: 'User input handling',
            resolved: true,
          },
        ]
        setErrors(mockErrors)
      }

      setIsLoading(false)
    }, 500)
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Tabs defaultValue="conversations" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
          <TabsList className="w-full md:w-auto grid grid-cols-3 md:flex">
            <TabsTrigger value="conversations">{t('bot.log.tabs.conversations')}</TabsTrigger>
            <TabsTrigger value="logs">{t('bot.log.tabs.logs')}</TabsTrigger>
            <TabsTrigger value="errors">{t('bot.log.tabs.errors')}</TabsTrigger>
          </TabsList>

          {/* Search and filter actions aligned with the tabs. */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="relative flex-1 md:w-48">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input placeholder={t('bot.log.filters.searchPlaceholder')} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-8 w-full" />
            </div>

            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[130px]">
                <Calendar className="h-4 w-4 mr-2" />
                <SelectValue placeholder={t('bot.log.filters.timeRange')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">{t('bot.log.filters.last24h')}</SelectItem>
                <SelectItem value="7d">{t('bot.log.filters.last7d')}</SelectItem>
                <SelectItem value="30d">{t('bot.log.filters.last30d')}</SelectItem>
                <SelectItem value="custom">{t('bot.log.filters.custom')}</SelectItem>
              </SelectContent>
            </Select>

            <Select value={logType} onValueChange={setLogType}>
              <SelectTrigger className="w-[130px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder={t('bot.log.filters.logType')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('bot.log.filters.all')}</SelectItem>
                <SelectItem value="info">{t('bot.log.filters.info')}</SelectItem>
                <SelectItem value="warning">{t('bot.log.filters.warning')}</SelectItem>
                <SelectItem value="error">{t('bot.log.filters.error')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <TabsContent value="conversations" className="mt-0">
          <ConversationTable conversations={conversations} isLoading={isLoading} currentPage={currentPage} setCurrentPage={setCurrentPage} />
        </TabsContent>

        <TabsContent value="logs" className="mt-0">
          <LogTable logs={logs} isLoading={isLoading} />
        </TabsContent>

        <TabsContent value="errors" className="mt-0">
          <ErrorTable errors={errors} isLoading={isLoading} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
