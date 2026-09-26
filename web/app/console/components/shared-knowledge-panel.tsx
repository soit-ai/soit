import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton } from './button'
import { DataStateRow } from './data-state'
import { ConsoleModal } from './modal'
import { Pager } from './pager'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import { WorkbenchPanel } from './workbench'
import { compactNumber, relativeTime } from '../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  listSharedKnowledge,
  queryKnowledge,
  type KnowledgeBase,
  type KnowledgeQueryResponse,
} from '@/services/knowledge-service'
import { requestErrorMessage } from '@/utils/request'

/**
 * Build › Knowledge › Shared: knowledge bases other workspaces of the tenant
 * share with this one. They are read here, never changed: a row opens a
 * query against it, run in its own workspace, where its owners see the read.
 */
export function SharedKnowledgePanel() {
  const { t } = useTranslation()
  const [target, setTarget] = useState<KnowledgeBase | null>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<KnowledgeQueryResponse | null>(null)

  const sharedQuery = useQuery({
    queryKey: ['console', 'knowledge', 'shared'],
    queryFn: () => listSharedKnowledge({ page_size: 100 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const rows = sharedQuery.data?.items || []

  const queryMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'shared', 'query'],
    mutationFn: () => queryKnowledge(target!.id, { query: question.trim(), top_k: 5 }),
    onSuccess: (result) => setAnswer(result),
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'The shared knowledge base could not be queried'))
    },
  })

  return (
    <WorkbenchPanel
      className="mt-3.5"
      title={t('console.knowledge.shared.title')}
      hint={t('console.knowledge.shared.hint')}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('console.knowledge.columns.name')}</TableHead>
            <TableHead>{t('console.knowledge.shared.from')}</TableHead>
            <TableHead className="num">{t('console.knowledge.columns.documents')}</TableHead>
            <TableHead className="num">{t('console.knowledge.columns.chunks')}</TableHead>
            <TableHead className="num">{t('console.knowledge.shared.updated')}</TableHead>
            <TableHead className="num" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <DataStateRow
              colSpan={6}
              isPending={sharedQuery.isPending}
              isError={sharedQuery.isError}
              emptyLabel={t('console.knowledge.shared.empty')}
            />
          ) : (
            rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <b style={{ fontWeight: 600 }}>{row.name}</b>
                  {row.description && (
                    <span className="dimmer" style={{ display: 'block', fontSize: 11 }}>
                      {row.description}
                    </span>
                  )}
                </TableCell>
                <TableCell className="mono dim">{row.workspace_id}</TableCell>
                <TableCell className="num dim">{compactNumber(row.doc_count)}</TableCell>
                <TableCell className="num dim">{compactNumber(row.chunk_count)}</TableCell>
                <TableCell className="num dimmer">{relativeTime(row.updated_at)}</TableCell>
                <TableCell className="num">
                  <ConsoleButton
                    size="sm"
                    onClick={() => {
                      setQuestion('')
                      setAnswer(null)
                      setTarget(row)
                    }}
                  >
                    {t('console.knowledge.shared.query')}
                  </ConsoleButton>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <Pager summary={t('console.knowledge.shared.note')} />

      <ConsoleModal
        open={target != null}
        onOpenChange={(open) => !open && setTarget(null)}
        title={t('console.knowledge.shared.queryTitle', { name: target?.name ?? '' })}
        note={t('console.knowledge.shared.queryNote')}
        confirmLabel={t('console.knowledge.shared.run')}
        confirmDisabled={!question.trim()}
        busy={queryMutation.isPending}
        onConfirm={() => queryMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.knowledge.shared.question')}</label>
          <input
            className="input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && question.trim()) queryMutation.mutate(undefined)
            }}
          />
        </div>
        {answer && (
          <div style={{ padding: '4px 16px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {answer.results.length === 0 ? (
              <span className="dimmer" style={{ fontSize: 12 }}>
                {t('console.knowledge.shared.noResults')}
              </span>
            ) : (
              answer.results.map((result) => (
                <div
                  key={result.chunk_id}
                  data-testid="shared-knowledge-result"
                  style={{ fontSize: 12, lineHeight: 1.55 }}
                >
                  <span className="mono dimmer" style={{ marginRight: 8 }}>
                    {result.score.toFixed(3)}
                  </span>
                  {result.text}
                </div>
              ))
            )}
          </div>
        )}
      </ConsoleModal>
    </WorkbenchPanel>
  )
}
