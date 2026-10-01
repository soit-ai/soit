import { useState } from 'react'

import { DataStateNote, DataStateRow } from './data-state'
import { ExpectationChips } from './evaluation-cases-panel'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import { WorkbenchPanel } from './workbench'
import { inputPreview, shortHash } from '../adapters/evaluations'
import { relativeTime } from '../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getDatasetVersion, listDatasetVersions, type Dataset } from '@/services/evaluation-service'

/** Added, removed and changed cases between a revision and the one before it. */
function Changes({ changes }: { changes: { added: number; removed: number; changed: number } }) {
  return (
    <span className="mono" style={{ fontSize: 11.5 }}>
      <span style={{ color: 'var(--success-foreground)' }}>+{changes.added}</span>{' '}
      <span style={{ color: 'var(--danger-foreground)' }}>−{changes.removed}</span>{' '}
      <span className="dim">~{changes.changed}</span>
    </span>
  )
}

/** The cases a revision held, so a report can be read against exactly what it ran. */
function VersionDetail({ datasetId, revision }: { datasetId: string; revision: number }) {
  const { t } = useTranslation()
  const detailQuery = useQuery({
    queryKey: ['console', 'evaluations', 'version', datasetId, revision],
    queryFn: () => getDatasetVersion(datasetId, revision, { suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const detail = detailQuery.data

  return (
    <WorkbenchPanel
      title={t('console.evaluations.versions.detail', { revision })}
      hint={detail ? <span className="mono">{shortHash(detail.content_hash)}</span> : undefined}
    >
      {!detail ? (
        <DataStateNote isPending={detailQuery.isPending} isError={detailQuery.isError} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.evaluations.cases.columns.name')}</TableHead>
              <TableHead>{t('console.evaluations.cases.columns.input')}</TableHead>
              <TableHead>{t('console.evaluations.cases.columns.expects')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {detail.snapshot.length === 0 ? (
              <DataStateRow
                colSpan={3}
                emptyLabel={t('console.evaluations.versions.emptySnapshot')}
              />
            ) : (
              detail.snapshot.map((item) => (
                <TableRow key={item.name}>
                  <TableCell style={{ overflowWrap: 'anywhere' }}>
                    <b style={{ fontWeight: 600 }}>{item.name}</b>
                  </TableCell>
                  <TableCell
                    className="mono dim"
                    style={{ fontSize: 11, maxWidth: 360, overflowWrap: 'anywhere' }}
                  >
                    {inputPreview(item.input)}
                  </TableCell>
                  <TableCell>
                    <ExpectationChips features={item.expected_features} />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      )}
    </WorkbenchPanel>
  )
}

/**
 * The Versions tab: one row per revision with its size, content hash and what
 * changed since the revision before. Two revisions with the same hash held the
 * same cases.
 */
export function EvaluationVersionsPanel({ dataset }: { dataset: Dataset }) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<number | null>(null)

  const versionsQuery = useQuery({
    queryKey: ['console', 'evaluations', 'versions', dataset.id, dataset.revision],
    queryFn: () => listDatasetVersions(dataset.id, { limit: 200 }, { suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const versions = versionsQuery.data || []

  return (
    <>
      <WorkbenchPanel
        title={t('console.evaluations.versions.title')}
        hint={t('console.evaluations.versions.hint')}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.evaluations.versions.columns.revision')}</TableHead>
              <TableHead className="num">
                {t('console.evaluations.versions.columns.cases')}
              </TableHead>
              <TableHead>{t('console.evaluations.versions.columns.changes')}</TableHead>
              <TableHead>{t('console.evaluations.versions.columns.hash')}</TableHead>
              <TableHead>{t('console.evaluations.versions.columns.note')}</TableHead>
              <TableHead className="num">
                {t('console.evaluations.versions.columns.when')}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {versions.length === 0 ? (
              <DataStateRow
                colSpan={6}
                isPending={versionsQuery.isPending}
                isError={versionsQuery.isError}
                emptyLabel={t('console.evaluations.versions.empty')}
              />
            ) : (
              versions.map((version) => (
                <TableRow
                  key={version.id}
                  className="rowlink cursor-pointer"
                  data-selected={version.revision === selected || undefined}
                  onClick={() => setSelected(version.revision)}
                >
                  <TableCell className="mono">
                    r{version.revision}
                    {version.revision === dataset.revision && (
                      <span className="dimmer"> · {t('console.evaluations.versions.current')}</span>
                    )}
                  </TableCell>
                  <TableCell className="num dim">{version.case_count}</TableCell>
                  <TableCell>
                    <Changes changes={version.changes} />
                  </TableCell>
                  <TableCell className="mono dim">{shortHash(version.content_hash)}</TableCell>
                  <TableCell className="dim" style={{ overflowWrap: 'anywhere' }}>
                    {version.note || '—'}
                  </TableCell>
                  <TableCell className="num dimmer">{relativeTime(version.created_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </WorkbenchPanel>
      {selected != null && <VersionDetail datasetId={dataset.id} revision={selected} />}
    </>
  )
}
