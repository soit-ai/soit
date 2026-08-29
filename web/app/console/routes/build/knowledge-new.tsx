import { useState } from 'react'

import { toast } from 'sonner'

import { Backlink, ConsoleButton, FilterChip, KeyValueList, StatusChip } from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useMutation } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { createKnowledgeBase } from '@/services/knowledge-service'
import { requestErrorMessage } from '@/utils/request'

const SOURCE_KINDS = ['Web crawl', 'File upload', 'Git sync', 'API push']

// BACKEND-PENDING: the estimate rail (pages discovered, chunk and time
// projections) has no endpoint to compute from before the first crawl.
export default function ConsoleKnowledgeNew() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [sourceKind, setSourceKind] = useState('Web crawl')
  const [name, setName] = useState('')
  const [sourceUri, setSourceUri] = useState('')
  const [depth, setDepth] = useState('3 levels')
  const [patterns, setPatterns] = useState(
    'include: /guides/**, /reference/**\nexclude: /blog/**, **/*.zip',
  )
  const [chunking, setChunking] = useState('auto · 512 tokens, 64 overlap')
  const [embedding, setEmbedding] = useState('bge-m3 · vllm self-hosted')
  const [rerank, setRerank] = useState('on · bge-reranker')
  const [schedule, setSchedule] = useState('nightly 02:00Z')
  const [visibility, setVisibility] = useState('workspace · all members')

  // The wizard's controls are richer than the create payload's typed fields, so
  // the source, schedule and pattern choices ride along in settings_json where
  // the ingest pipeline reads them.
  const createMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'create'],
    mutationFn: () =>
      createKnowledgeBase(
        {
          name: name.trim(),
          knowledge_type: 'document',
          visibility: visibility.startsWith('workspace') ? 'workspace' : 'restricted',
          settings_json: {
            source_kind: sourceKind,
            source_uri: sourceUri.trim() || undefined,
            crawl_depth: depth,
            patterns,
            sync_schedule: schedule,
          },
          chunking_json: { preset: chunking },
          retrieval_json: { use_rerank: rerank.startsWith('on') },
          default_embedding_model_ref: embedding,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: (knowledge) => {
      navigate(`/v2/build/knowledge/${knowledge.id}`)
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to create the knowledge base'))
    },
  })

  return (
    <>
      <Backlink to="/v2/build/knowledge">{t('console.knowNew.back')}</Backlink>
      <div className="page-head">
        <h1>{t('console.knowNew.title')}</h1>
        <StatusChip status="info" label="DRAFT" />
      </div>

      <div className="rdgrid">
        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <span className="stepno">STEP 1</span>
              <h2>{t('console.knowNew.step1')}</h2>
              <span className="hint">{t('console.knowNew.step1Hint')}</span>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.name')}</label>
              <input
                className="input"
                placeholder="product-docs"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.sourceKind')}</label>
              <div className="checks" style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
                {SOURCE_KINDS.map((kind) => (
                  <FilterChip key={kind} active={sourceKind === kind} onClick={() => setSourceKind(kind)}>
                    {kind}
                  </FilterChip>
                ))}
              </div>
            </div>
            <div className="frow">
              <label>
                {t('console.knowNew.fields.startUrl')}
                <small>{t('console.knowNew.fields.startUrlHint')}</small>
              </label>
              <input
                className="input"
                placeholder="https://docs.acme.io"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
                value={sourceUri}
                onChange={(event) => setSourceUri(event.target.value)}
              />
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.depth')}</label>
              <select
                className="input"
                style={{ maxWidth: 140 }}
                value={depth}
                onChange={(event) => setDepth(event.target.value)}
              >
                <option>3 levels</option>
                <option>2 levels</option>
                <option>unlimited</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.knowNew.fields.include')}
                <small>{t('console.knowNew.fields.includeHint')}</small>
              </label>
              <textarea
                className="input"
                value={patterns}
                onChange={(event) => setPatterns(event.target.value)}
              />
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <span className="stepno">STEP 2</span>
              <h2>{t('console.knowNew.step2')}</h2>
              <span className="hint">{t('console.knowNew.step2Hint')}</span>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.chunking')}</label>
              <select
                className="input"
                value={chunking}
                onChange={(event) => setChunking(event.target.value)}
              >
                <option>auto · 512 tokens, 64 overlap</option>
                <option>auto · 1024 tokens</option>
                <option>by heading</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.embedding')}</label>
              <select
                className="input"
                value={embedding}
                onChange={(event) => setEmbedding(event.target.value)}
              >
                <option>bge-m3 · vllm self-hosted</option>
                <option>voyage-3</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.rerank')}</label>
              <select
                className="input"
                style={{ maxWidth: 200 }}
                value={rerank}
                onChange={(event) => setRerank(event.target.value)}
              >
                <option>on · bge-reranker</option>
                <option>off</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.schedule')}</label>
              <select
                className="input"
                style={{ maxWidth: 200 }}
                value={schedule}
                onChange={(event) => setSchedule(event.target.value)}
              >
                <option>nightly 02:00Z</option>
                <option>hourly</option>
                <option>manual only</option>
              </select>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <span className="stepno">STEP 3</span>
              <h2>{t('console.knowNew.step3')}</h2>
              <span className="hint">{t('console.knowNew.step3Hint')}</span>
            </div>
            <div className="frow">
              <label>
                {t('console.knowNew.fields.bind')}
                <small>{t('console.knowNew.fields.bindHint')}</small>
              </label>
              <div className="checks">
                <label>
                  <input type="checkbox" defaultChecked />
                  support-triage
                </label>
                <label>
                  <input type="checkbox" />
                  ops-copilot
                </label>
                <label>
                  <input type="checkbox" />
                  release-notes
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.visibility')}</label>
              <select
                className="input"
                style={{ maxWidth: 240 }}
                value={visibility}
                onChange={(event) => setVisibility(event.target.value)}
              >
                <option>workspace · all members</option>
                <option>restricted · selected teams</option>
              </select>
            </div>
          </div>

          <div className="actionbar">
            <span className="note">{t('console.knowNew.note')}</span>
            <ConsoleButton onClick={() => navigate('/v2/build/knowledge')}>
              {t('console.knowNew.cancel')}
            </ConsoleButton>
            <ConsoleButton>{t('console.knowNew.saveDraft')}</ConsoleButton>
            <ConsoleButton
              variant="primary"
              disabled={!name.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate(undefined)}
            >
              {t('console.knowNew.create')}
            </ConsoleButton>
          </div>
        </div>

        <div className="rail">
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.knowNew.estimate')}</h2>
            </div>
            <KeyValueList
              items={[
                { key: 'Pages discovered', value: '~1,180' },
                { key: 'Est. chunks', value: '~18,000' },
                { key: 'Est. embed time', value: '~22 min' },
                { key: 'Est. embed cost', value: '$0.00 · self-hosted' },
              ]}
            />
          </div>
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.knowNew.governance')}</h2>
            </div>
            <KeyValueList
              items={[
                { key: 'Ingest runs as', value: 'governed task' },
                { key: 'Citations', value: 'chunk-version pinned' },
                { key: 'Egress', value: 'crawl host allowlisted' },
              ]}
            />
          </div>
        </div>
      </div>
    </>
  )
}
