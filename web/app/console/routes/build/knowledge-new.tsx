import { useState } from 'react'

import { Backlink, ConsoleButton, FilterChip, KeyValueList, StatusChip } from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useTranslation } from '@/i18n'

const SOURCE_KINDS = ['Web crawl', 'File upload', 'Git sync', 'API push']

// BACKEND-PENDING: knowledge-service create + ingest estimate endpoints.
export default function ConsoleKnowledgeNew() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [sourceKind, setSourceKind] = useState('Web crawl')

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
              <input className="input" placeholder="product-docs" />
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
              />
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.depth')}</label>
              <select className="input" style={{ maxWidth: 140 }} defaultValue="3 levels">
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
                defaultValue={'include: /guides/**, /reference/**\nexclude: /blog/**, **/*.zip'}
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
              <select className="input" defaultValue="auto · 512 tokens, 64 overlap">
                <option>auto · 512 tokens, 64 overlap</option>
                <option>auto · 1024 tokens</option>
                <option>by heading</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.embedding')}</label>
              <select className="input" defaultValue="bge-m3 · vllm self-hosted">
                <option>bge-m3 · vllm self-hosted</option>
                <option>voyage-3</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.rerank')}</label>
              <select className="input" style={{ maxWidth: 200 }} defaultValue="on · bge-reranker">
                <option>on · bge-reranker</option>
                <option>off</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.knowNew.fields.schedule')}</label>
              <select className="input" style={{ maxWidth: 200 }} defaultValue="nightly 02:00Z">
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
              <select className="input" style={{ maxWidth: 240 }} defaultValue="workspace · all members">
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
            <ConsoleButton variant="primary" onClick={() => navigate('/v2/build/knowledge')}>
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
