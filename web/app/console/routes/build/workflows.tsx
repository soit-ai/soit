import { useRef, useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  ConsoleTabs,
  DataStateRow,
  FilterChip,
  FilterSearch,
  Hist,
  IconExport,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
  outcomePattern,
  type ConsoleStatus,
} from '../../components'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { compactNumber, latency, percent, relativeTime } from '../../adapters/palette'
import { usePageCursor } from '../../adapters/use-page-cursor'
import { readDocumentFile } from '../../adapters/read-document-file'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  createWorkflow,
  deleteWorkflow,
  getWorkflow,
  getWorkflowWorkbench,
  importWorkflowDsl,
  publishWorkflowVersion,
  type WorkflowWorkbenchRow,
} from '@/services/workflow-service'
import { requestErrorMessage } from '@/utils/request'

type WfTab = 'all' | 'publish' | 'archived'
type WfFilter = 'all' | 'published' | 'draft'

const PAGE_SIZE = 50

/**
 * The workbench row carries a lifecycle status, not a run verdict; map it onto
 * the shared console vocabulary so the chip reads the same as everywhere else.
 */
const STATUS_TO_CONSOLE: Record<WorkflowWorkbenchRow['status'], ConsoleStatus> = {
  running: 'running',
  publishing: 'staged',
  abnormal: 'failed',
  draft: 'draft',
}

export default function ConsoleWorkflows() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<WfTab>('all')
  const [filter, setFilter] = useState<WfFilter>('all')
  const [search, setSearch] = useState('')

  const cursor = usePageCursor()
  const workbenchQuery = useQuery({
    queryKey: ['console', 'workflows', 'workbench', cursor.pageToken],
    queryFn: () => getWorkflowWorkbench({ page_token: cursor.pageToken, page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const summary = workbenchQuery.data?.summary
  const tabCounts = workbenchQuery.data?.tabs
  const allRows = workbenchQuery.data?.items || []

  const [publishTarget, setPublishTarget] = useState<WorkflowWorkbenchRow | null>(null)
  const [archiving, setArchiving] = useState<WorkflowWorkbenchRow | null>(null)

  const afterWrite = () => {
    void workbenchQuery.refetch()
    setPublishTarget(null)
    setArchiving(null)
  }

  const publishMutation = useMutation({
    mutationKey: ['console', 'workflows', 'publish'],
    // The workbench row carries no version id, so the workflow record supplies
    // the draft to promote — publishing whatever is current, as the builder does.
    mutationFn: async () => {
      const workflow = await getWorkflow(publishTarget!.id, { suppressErrorToast: true })
      const versionId = workflow.current_version_id
      if (!versionId) throw new Error('This workflow has no draft version to publish')
      return publishWorkflowVersion(publishTarget!.id, versionId)
    },
    onSuccess: afterWrite,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to publish the workflow'))
    },
  })

  const archiveMutation = useMutation({
    mutationKey: ['console', 'workflows', 'archive'],
    mutationFn: () => deleteWorkflow(archiving!.id, { suppressErrorToast: true }),
    onSuccess: afterWrite,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to archive the workflow'))
    },
  })

  // A DSL file imports into an existing workflow, so importing from the list
  // creates one first, named after the DSL (or the file), and archives it
  // again if the DSL is refused, rather than leaving an empty workflow.
  const importInput = useRef<HTMLInputElement>(null)
  const importMutation = useMutation({
    mutationKey: ['console', 'workflows', 'import'],
    mutationFn: async (file: File) => {
      const dsl = await readDocumentFile(file)
      const named = typeof dsl.name === 'string' && dsl.name.trim() ? dsl.name.trim() : ''
      const workflow = await createWorkflow(
        {
          name: named || file.name.replace(/\.(ya?ml|json)$/i, ''),
          description: typeof dsl.description === 'string' ? dsl.description : undefined,
        },
        { suppressErrorToast: true },
      )
      try {
        await importWorkflowDsl(workflow.id, { dsl, format: 'json' })
      } catch (error) {
        await deleteWorkflow(workflow.id, { suppressErrorToast: true }).catch(() => undefined)
        throw error
      }
      return workflow
    },
    onSuccess: (workflow) => {
      toast.success(t('console.workflows.imported', { name: workflow.name }))
      void workbenchQuery.refetch()
      navigate(`/build/workflows/${workflow.id}`)
    },
    onError: (error: unknown) => {
      toast.error(requestErrorMessage(error, t('console.workflows.importFailed')))
    },
  })

  const matchesSearch = (row: WorkflowWorkbenchRow) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.name, row.summary, row.description]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  }

  const draftCount = allRows.filter((row) => row.status === 'draft').length
  const publishedCount = allRows.length - draftCount

  const rows = allRows.filter((row) => {
    if (filter === 'published' && row.status === 'draft') return false
    if (filter === 'draft' && row.status !== 'draft') return false
    return matchesSearch(row)
  })

  const publishing = allRows.filter((row) => row.status === 'publishing')

  return (
    <Workbench
      title={t('console.workflows.title')}
      description={t('console.workflows.description')}
      actions={
        <>
          <input
            ref={importInput}
            type="file"
            accept=".yaml,.yml,.json,application/json,application/yaml,text/yaml"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ''
              if (file) importMutation.mutate(file)
            }}
          />
          <ConsoleButton
            title={t('console.workflows.importHint')}
            disabled={importMutation.isPending}
            onClick={() => importInput.current?.click()}
          >
            <IconExport />
            {t('console.workflows.import')}
          </ConsoleButton>
          <ConsoleButton variant="primary" onClick={() => navigate('/build/workflows/new')}>
            <IconPlus />
            {t('console.workflows.newWorkflow')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.workflows.tiles.workflows')}
            value={summary ? compactNumber(summary.total_workflows) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                {summary
                  ? `${summary.published_workflows} published · ${tabCounts?.draft ?? draftCount} draft`
                  : t('console.common.loading')}
              </span>
            }
          />
          <StatTile
            label={t('console.workflows.tiles.runs')}
            value={summary ? compactNumber(summary.today_runs) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">{t('console.tileSubs.today')}</span>}
          />
          <StatTile
            label={t('console.workflows.tiles.success')}
            value={summary ? percent(summary.success_rate) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">p50 {latency(summary?.avg_latency_ms)}</span>}
          />
          <StatTile
            label={t('console.workflows.tiles.attention')}
            value={summary ? String(summary.recent_exceptions) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">{t('console.tileSubs.recentExceptions')}</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'all', label: t('console.workflows.tabs.all'), count: tabCounts?.all ?? allRows.length },
            { id: 'publish', label: t('console.workflows.tabs.publish'), count: tabCounts?.publishing ?? publishing.length },
            { id: 'archived', label: t('console.workflows.tabs.archived') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'all' ? (
          <>
            {(
              [
                ['all', t('console.workflows.filters.all'), allRows.length],
                ['published', t('console.workflows.filters.published'), publishedCount],
                ['draft', t('console.workflows.filters.draft'), draftCount],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterChip>{t('console.workflows.filters.triggerAny')}</FilterChip>
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.workflows.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'all' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.workflows.columns.workflow')}</TableHead>
                <TableHead>{t('console.workflows.columns.version')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.nodes')}</TableHead>
                <TableHead>{t('console.workflows.columns.lastRun')}</TableHead>
                <TableHead>{t('console.workflows.columns.outcomes')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.success')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.updated')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={7}
                  isPending={workbenchQuery.isPending}
                  isError={workbenchQuery.isError}
                />
              ) : (
                rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="rowlink cursor-pointer"
                    onClick={() => navigate(`/build/workflows/${row.id}`)}
                  >
                    <TableCell>
                      <b style={{ fontWeight: 600 }}>{row.name}</b>
                      <br />
                      <span className="dimmer" style={{ fontSize: 11 }}>
                        {row.summary || row.description || '—'}
                      </span>
                    </TableCell>
                    <TableCell className="mono dim">{row.status}</TableCell>
                    <TableCell className="num dim">{row.node_count ?? '—'}</TableCell>
                    <TableCell>
                      <StatusChip
                        status={STATUS_TO_CONSOLE[row.status]}
                        label={relativeTime(row.last_run_at)}
                      />
                    </TableCell>
                    <TableCell>
                      <Hist pattern={outcomePattern(row.recent_outcomes ?? [])} label="last 28 run outcomes" />
                    </TableCell>
                    <TableCell className="num dim">{percent(row.success_rate)}</TableCell>
                    <TableCell className="num dimmer">{relativeTime(row.updated_at)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'all' && (cursor.hasPrevious || workbenchQuery.data?.next_page_token) && (
        <Pager
          className="mt-3.5"
          summary={t('console.common.pageFilterNote')}
          onPrev={cursor.prev}
          onNext={() => cursor.next(workbenchQuery.data?.next_page_token)}
          prevDisabled={!cursor.hasPrevious}
          nextDisabled={!workbenchQuery.data?.next_page_token}
          prevLabel={t('console.runs.prev')}
          nextLabel={t('console.runs.next')}
        />
      )}

      {tab === 'publish' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.workflows.publishTitle')}
          hint={t('console.workflows.publishHint')}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.workflows.columns.workflow')}</TableHead>
                <TableHead>{t('console.workflows.columns.version')}</TableHead>
                <TableHead>{t('console.workflows.columns.gate')}</TableHead>
                <TableHead>{t('console.workflows.columns.requestedBy')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.waiting')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {publishing.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={workbenchQuery.isPending}
                  isError={workbenchQuery.isError}
                />
              ) : (
                publishing.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <b style={{ fontWeight: 600 }}>{row.name}</b>
                    </TableCell>
                    <TableCell className="mono dim">{row.status}</TableCell>
                    <TableCell>
                      {/* No validation-gate endpoint: the workbench only reports
                          that the workflow is mid-publish, plus its exception
                          count. Report exactly that. */}
                      <StatusChip status={row.recent_exception_count > 0 ? 'warn' : 'staged'} />{' '}
                      <span className="dimmer" style={{ fontSize: 10.5 }}>
                        {row.summary || row.description || '—'}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{row.owner || '—'}</TableCell>
                    <TableCell className="num dim">{relativeTime(row.updated_at)}</TableCell>
                    <TableCell className="num">
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <ConsoleButton size="sm" onClick={() => navigate(`/build/workflows/${row.id}`)}>
                          {t('console.workflows.openBuilder')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="primary"
                          size="sm"
                          onClick={() => setPublishTarget(row)}
                        >
                          {t('console.workflows.publishAction')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          style={{ color: 'var(--danger-foreground)' }}
                          onClick={() => setArchiving(row)}
                        >
                          {t('console.workflows.archiveAction')}
                        </ConsoleButton>
                      </span>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.workflows.publishNote')} />
        </WorkbenchPanel>
      )}

      {/* Archiving a workflow only flips deleted_at (DELETE /workflows/{id});
          there is no list endpoint for soft-deleted workflows. Show the
          retention promise rather than fixtures. */}
      {tab === 'archived' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.workflows.archivedEmpty')}
            <span className="mono">{t('console.workflows.archivedRestore')}</span>
          </div>
        </WorkbenchPanel>
      )}

      <ConsoleModal
        open={publishTarget != null}
        onOpenChange={(open) => !open && setPublishTarget(null)}
        title={t('console.workflows.publishTitleModal')}
        note={t('console.workflows.publishModalNote')}
        confirmLabel={t('console.workflows.publishAction')}
        busy={publishMutation.isPending}
        onConfirm={() => publishMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.workflows.publishConfirm', { name: publishTarget?.name ?? '' })}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={archiving != null}
        onOpenChange={(open) => !open && setArchiving(null)}
        title={t('console.workflows.archiveTitle')}
        confirmLabel={t('console.workflows.archiveAction')}
        destructive
        busy={archiveMutation.isPending}
        onConfirm={() => archiveMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.workflows.archiveConfirm', { name: archiving?.name ?? '' })}
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
