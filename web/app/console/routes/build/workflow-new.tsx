import { useState } from 'react'

import { Backlink, ConsoleButton } from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

const TEMPLATES = [
  { id: 'blank', name: 'Blank canvas', description: 'Start from an empty graph. Input and output nodes are placed for you.', nodes: 2, colors: ['var(--cat-amber)', 'var(--cat-teal)'] },
  { id: 'ticket', name: 'Ticket escalation', description: 'Classify → branch on confidence → route or human-review. The flow this workspace runs in production.', nodes: 8, colors: ['var(--cat-amber)', 'var(--cat-pink)', 'var(--cat-blue)', 'var(--cat-indigo)', 'var(--cat-cyan)', 'var(--cat-purple)'] },
  { id: 'sync', name: 'Nightly knowledge sync', description: 'Crawl → chunk → embed → verify drift, checkpointed per stage for resume.', nodes: 12, colors: ['var(--cat-amber)', 'var(--cat-cyan)', 'var(--cat-blue)', 'var(--cat-teal)'] },
  { id: 'report', name: 'Report with approval', description: 'Collect → summarize → mandatory human-approval gate → publish artifact.', nodes: 5, colors: ['var(--cat-amber)', 'var(--cat-blue)', 'var(--cat-purple)', 'var(--cat-teal)'] },
]

export default function ConsoleWorkflowNew() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [selected, setSelected] = useState('blank')

  return (
    <>
      <Backlink to="/v2/build/workflows">{t('console.wfNew.back')}</Backlink>
      <div className="page-head">
        <h1>{t('console.wfNew.title')}</h1>
      </div>

      <div className="panel" style={{ marginBottom: 12 }}>
        <div className="frow">
          <label>{t('console.wfNew.name')}</label>
          <input className="input" placeholder="my-workflow" />
        </div>
        <div className="frow">
          <label>{t('console.wfNew.description')}</label>
          <input className="input" placeholder="What this workflow does" />
        </div>
      </div>

      <div className="cards" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
        {TEMPLATES.map((template) => (
          <div
            key={template.id}
            className={cn('acard tplcard', selected === template.id && 'sel')}
            onClick={() => setSelected(template.id)}
          >
            <b style={{ fontWeight: 600 }}>{template.name}</b>
            <p>{template.description}</p>
            <div className="acard-foot">
              <span className="tpl-nodes">
                {template.colors.map((color) => (
                  <i key={color} style={{ '--c': color } as React.CSSProperties} />
                ))}
              </span>
              <span className="mono dimmer" style={{ fontSize: 10 }}>
                {t('console.wfNew.nodes', { count: template.nodes })}
              </span>
              <span className="spacer" />
              <ConsoleButton
                variant={selected === template.id ? 'primary' : 'default'}
                size="sm"
                onClick={(event) => {
                  event.stopPropagation()
                  navigate('/v2/build/workflows/new-draft')
                }}
              >
                {t('console.wfNew.useTemplate')}
              </ConsoleButton>
            </div>
          </div>
        ))}
      </div>
      <div className="actionbar">
        <span className="note">{t('console.wfNew.note')}</span>
      </div>
    </>
  )
}
