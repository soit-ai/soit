import { Search, Filter, Calendar } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTranslation } from '@/i18n'

type LogFilterProps = {
  searchQuery: string
  setSearchQuery: (value: string) => void
  timeRange: string
  setTimeRange: (value: string) => void
  logType: string
  setLogType: (value: string) => void
}

export function LogFilter({
  searchQuery,
  setSearchQuery,
  timeRange,
  setTimeRange,
  logType,
  setLogType
}: LogFilterProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center gap-2 my-4">
      <div className="relative flex-1">
        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t('bot.log.filters.searchPlaceholder')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8"
        />
      </div>
      
      <Select value={timeRange} onValueChange={setTimeRange}>
        <SelectTrigger className="w-[180px]">
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
        <SelectTrigger className="w-[180px]">
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
  )
}
