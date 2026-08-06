import { RefreshCw, Search, SlidersHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import type {
  DashboardSection as DashboardSectionModel,
  DashboardTab,
  ObserveBucket,
  ObserveRange,
  ObserveTabId,
} from '@/services/observe-service'

import { MetricTile } from './dashboard-summary'
import {
  cardChrome,
  OBSERVE_BUCKETS,
  OBSERVE_RANGES,
} from './dashboard-utils'
import { SectionCharts } from './section-charts'
import { SectionTable } from './section-table'

type DashboardSectionProps = {
  tab: ObserveTabId
  range: ObserveRange
  bucket: ObserveBucket
  q: string
  pageSize: number
  pageToken?: string
  tabs: DashboardTab[]
  section: DashboardSectionModel
  onUpdateParams: (patch: Record<string, string | undefined>) => void
  onRefresh: () => void
  onOpenRuns: (row: Record<string, unknown>) => void
  onOpenDetail: (row: Record<string, unknown>) => void
}

export function DashboardSection({
  tab,
  range,
  bucket,
  q,
  pageSize,
  pageToken,
  tabs,
  section,
  onUpdateParams,
  onRefresh,
  onOpenRuns,
  onOpenDetail,
}: DashboardSectionProps) {
  const { t } = useTranslation()

  return (
    <Card className={cn('overflow-hidden', cardChrome)}>
      <CardContent className="p-0">
        <Tabs value={tab} onValueChange={(value) => onUpdateParams({ tab: value, page_token: undefined, q: undefined })}>
          <div className="flex flex-col gap-3 border-b px-4 py-2.5 xl:flex-row xl:items-center xl:justify-between">
            <TabsList variant="line" className="max-w-full flex-wrap justify-start">
              {tabs.map((item) => <TabsTrigger key={item.id} value={item.id} className="h-9 px-4 data-[state=active]:text-blue-600 dark:data-[state=active]:text-blue-300">{item.label}</TabsTrigger>)}
            </TabsList>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
              <div className="relative min-w-[240px] sm:w-[300px]">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={q} onChange={(event) => onUpdateParams({ q: event.target.value, page_token: undefined })} placeholder={t('observe.filters.searchPlaceholder')} className="h-9 rounded-lg bg-panel pl-9" />
              </div>
              <Button variant="outline" className="h-9 rounded-lg bg-panel" type="button"><SlidersHorizontal className="h-4 w-4" />{t('observe.filters.filter')}</Button>
              <select aria-label={t('observe.filters.range')} className="h-9 rounded-lg border bg-panel px-3 text-sm" value={range} onChange={(event) => onUpdateParams({ range: event.target.value, page_token: undefined })}>
                {OBSERVE_RANGES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <select aria-label={t('observe.filters.bucket')} className="h-9 rounded-lg border bg-panel px-3 text-sm" value={bucket} onChange={(event) => onUpdateParams({ bucket: event.target.value, page_token: undefined })}>
                {OBSERVE_BUCKETS.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <Button variant="outline" size="icon" className="h-9 w-9 rounded-lg bg-panel" aria-label={t('observe.filters.refreshView')} onClick={onRefresh}><RefreshCw className="h-4 w-4" /></Button>
            </div>
          </div>

          <TabsContent value={tab} className="m-0 space-y-3 p-4">
            <SectionCharts section={section} />
            {section.id === 'knowledge_quality' ? <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
              {section.summary_cards.map((card) => <MetricTile key={card.id} item={card} />)}
            </div> : null}
            <SectionTable section={section} onOpenRuns={onOpenRuns} onOpenDetail={onOpenDetail} />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-1 text-sm text-muted-foreground">
              <span>{t('observe.pagination.total', { value: section.page.total_count })}</span>
              <div className="flex flex-wrap items-center gap-2">
                <select aria-label={t('observe.pagination.pageSizeLabel')} className="h-8 rounded-lg border bg-panel px-3 text-xs" value={pageSize} onChange={(event) => onUpdateParams({ page_size: event.target.value, page_token: undefined })}>
                  <option value="10">{t('observe.pagination.pageSize', { size: 10 })}</option>
                  <option value="20">{t('observe.pagination.pageSize', { size: 20 })}</option>
                  <option value="50">{t('observe.pagination.pageSize', { size: 50 })}</option>
                </select>
                {/* The API paginates by token, so only first/next moves exist. */}
                <Button variant="ghost" size="icon-sm" disabled={!pageToken} onClick={() => onUpdateParams({ page_token: undefined })}>‹</Button>
                <Button variant="ghost" size="icon-sm" disabled={!section.page.next_page_token} onClick={() => onUpdateParams({ page_token: section.page.next_page_token || undefined })}>›</Button>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
