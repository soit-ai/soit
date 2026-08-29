import { useEffect, useState } from 'react'
import {
  Bot,
  Box,
  BrainCog,
  History,
  LoaderCircle,
  MessageSquare,
  Search,
  ScrollText,
  Workflow,
} from 'lucide-react'
import { useSearchParams } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import {
  searchWorkspace,
  type GlobalSearchResult,
  type SearchKind,
} from '@/services/global-search-service'

const SEARCH_KINDS: SearchKind[] = [
  'agent',
  'workflow',
  'knowledge',
  'plugin',
  'model',
  'thread',
  'run',
]

const KIND_ICONS = {
  agent: Bot,
  workflow: Workflow,
  knowledge: ScrollText,
  plugin: Box,
  model: BrainCog,
  thread: MessageSquare,
  run: History,
} satisfies Record<SearchKind, typeof Bot>

export default function GlobalSearchPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const query = (searchParams.get('q') || '').trim()
  const requestedKind = searchParams.get('type')
  const selectedKind = SEARCH_KINDS.includes(requestedKind as SearchKind)
    ? requestedKind as SearchKind
    : null
  const [draftQuery, setDraftQuery] = useState(query)
  const [items, setItems] = useState<GlobalSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setDraftQuery(query)
  }, [query])

  useEffect(() => {
    let active = true
    if (query.length < 2) {
      setItems([])
      setLoading(false)
      setFailed(false)
      return () => {
        active = false
      }
    }
    setLoading(true)
    setFailed(false)
    void searchWorkspace(query, {
      types: selectedKind ? [selectedKind] : undefined,
      limit: 10,
    })
      .then((response) => {
        if (active) setItems(response.items || [])
      })
      .catch((error) => {
        console.error('Failed to search workspace:', error)
        if (active) {
          setItems([])
          setFailed(true)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [query, selectedKind])

  const submitSearch = () => {
    const normalized = draftQuery.trim()
    if (normalized.length < 2) return
    const next = new URLSearchParams()
    next.set('q', normalized)
    if (selectedKind) next.set('type', selectedKind)
    setSearchParams(next)
  }

  const selectKind = (kind: SearchKind | null) => {
    const next = new URLSearchParams(searchParams)
    if (kind) next.set('type', kind)
    else next.delete('type')
    setSearchParams(next)
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 p-4 sm:p-6 lg:p-8">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Search className="size-5 text-primary" />
          <h1 className="text-xl font-bold tracking-tight">{t('layout.search.title')}</h1>
        </div>
        <p className="text-sm text-muted-foreground">{t('layout.search.description')}</p>
      </div>

      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          submitSearch()
        }}
      >
        <Input
          type="search"
          aria-label={t('layout.search.inputLabel')}
          value={draftQuery}
          placeholder={t('layout.header.searchPlaceholder')}
          onChange={(event) => setDraftQuery(event.target.value)}
        />
        <Button type="submit" disabled={draftQuery.trim().length < 2}>{t('layout.search.action')}</Button>
      </form>

      <div className="flex flex-wrap gap-2" aria-label={t('layout.search.filtersLabel')}>
        <Button
          size="sm"
          variant={selectedKind === null ? 'default' : 'outline'}
          aria-pressed={selectedKind === null}
          onClick={() => selectKind(null)}
        >
          {t('layout.search.kinds.all')}
        </Button>
        {SEARCH_KINDS.map((kind) => (
          <Button
            key={kind}
            size="sm"
            variant={selectedKind === kind ? 'default' : 'outline'}
            aria-pressed={selectedKind === kind}
            onClick={() => selectKind(kind)}
          >
            {t(`layout.search.kinds.${kind}`)}
          </Button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {query.length >= 2
            ? t('layout.search.resultSummary', { count: items.length, query })
            : t('layout.search.startHint')}
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin" />
          {t('layout.search.loading')}
        </div>
      ) : failed ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-destructive">{t('layout.search.failed')}</CardContent>
        </Card>
      ) : items.length ? (
        <div className="grid gap-3">
          {items.map((item) => {
            const Icon = KIND_ICONS[item.kind]
            return (
              <Button
                key={`${item.kind}:${item.id}`}
                variant="outline"
                aria-label={item.title}
                className="h-auto min-h-20 w-full justify-start gap-4 px-4 py-3 text-left"
                onClick={() => navigate(item.url)}
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="size-5 text-primary" />
                </span>
                <span className="min-w-0 flex-1 space-y-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-semibold">{item.title}</span>
                    <Badge variant="secondary">{t(`layout.search.kinds.${item.kind}`)}</Badge>
                    {item.status && <Badge variant="outline">{item.status}</Badge>}
                  </span>
                  {item.subtitle && <span className="block truncate text-xs text-muted-foreground">{item.subtitle}</span>}
                  <span className="block font-mono text-[11px] text-muted-foreground">{item.id}</span>
                </span>
              </Button>
            )
          })}
        </div>
      ) : query.length >= 2 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="font-medium">{t('layout.search.emptyTitle')}</p>
            <p className="mt-1 text-sm text-muted-foreground">{t('layout.search.emptyDescription')}</p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
