import { useState } from 'react'

import { toast } from 'sonner'

import { Backlink, ConsoleButton, FilterChip, KeyValueList, StatusChip } from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { CHUNKING_PRESET_KEYS, CHUNKING_PRESETS, type ChunkingPreset } from '../../adapters/chunking'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { createKnowledgeBase, type KnowledgeVisibility } from '@/services/knowledge-service'
import { listModels } from '@/services/provider-service'
import { requestErrorMessage } from '@/utils/request'

const SOURCE_KINDS = ['Web crawl', 'File upload', 'Git sync', 'API push']

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
  const [chunking, setChunking] = useState<ChunkingPreset>('default')
  const [embedding, setEmbedding] = useState('')
  const [rerank, setRerank] = useState(true)
  const [visibility, setVisibility] = useState<KnowledgeVisibility>('workspace')

  // The embedding model becomes the library's first index; only a model the
  // workspace serves for embeddings is offered, and none means "choose when
  // creating the first index".
  const modelsQuery = useQuery({
    queryKey: ['console', 'models', 'embedding'],
    queryFn: () => listModels(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const embeddingModels = (modelsQuery.data || []).filter(
    (model) => model.modelType === 'embedding' && model.isActive,
  )

  // The source, depth and pattern choices ride along in settings_json, which
  // the ingest pipeline reads; chunking and rerank map onto the fields the
  // pipeline and retrieval read.
  const createMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'create'],
    mutationFn: () =>
      createKnowledgeBase(
        {
          name: name.trim(),
          knowledge_type: 'document',
          visibility,
          settings_json: {
            source_kind: sourceKind,
            source_uri: sourceUri.trim() || undefined,
            crawl_depth: depth,
            patterns,
          },
          chunking_json: { ...CHUNKING_PRESETS[chunking] },
          retrieval_json: { use_rerank: rerank },
          ...(embedding ? { default_embedding_model_ref: embedding } : {}),
        },
        { suppressErrorToast: true },
      ),
    onSuccess: (knowledge) => {
      navigate(`/build/knowledge/${knowledge.id}`)
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to create the knowledge base'))
    },
  })

  return (
    <>
      <Backlink to="/build/knowledge">{t('console.knowNew.back')}</Backlink>
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
                onChange={(event) => setChunking(event.target.value as ChunkingPreset)}
              >
                {CHUNKING_PRESET_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {t(`console.knowledgeChunking.${key}`)}
                  </option>
                ))}
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.knowNew.fields.embedding')}
                <small>{t('console.knowNew.fields.embeddingHint')}</small>
              </label>
              <select
                className="input"
                value={embedding}
                onChange={(event) => setEmbedding(event.target.value)}
              >
                <option value="">{t('console.knowNew.fields.embeddingLater')}</option>
                {embeddingModels.map((model) => (
                  <option key={model.modelName} value={model.modelName}>
                    {model.name} · {model.providerName}
                  </option>
                ))}
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.knowNew.fields.rerank')}
                <small>{t('console.knowNew.fields.rerankHint')}</small>
              </label>
              <select
                className="input"
                style={{ maxWidth: 200 }}
                value={rerank ? 'on' : 'off'}
                onChange={(event) => setRerank(event.target.value === 'on')}
              >
                <option value="on">{t('console.knowNew.fields.rerankOn')}</option>
                <option value="off">{t('console.knowNew.fields.rerankOff')}</option>
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
                style={{ maxWidth: 320 }}
                value={visibility}
                onChange={(event) => setVisibility(event.target.value as KnowledgeVisibility)}
              >
                <option value="workspace">{t('console.knowledgeVisibility.workspace')}</option>
                <option value="private">{t('console.knowledgeVisibility.private')}</option>
              </select>
            </div>
          </div>

          <div className="actionbar">
            <span className="note">{t('console.knowNew.note')}</span>
            <ConsoleButton onClick={() => navigate('/build/knowledge')}>
              {t('console.knowNew.cancel')}
            </ConsoleButton>
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
