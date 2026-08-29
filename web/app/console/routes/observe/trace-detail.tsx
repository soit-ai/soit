import { useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  IconChevronRight,
  IconExport,
  KeyValueList,
  StatusChip,
  TBar,
  WorkbenchPanel,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { mockTraceDetail } from '../../mocks/observe'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

// BACKEND-PENDING: observe-service span query replaces the fixture; the
// waterfall is shared with the run ledger view by design.
export default function ConsoleTraceDetail() {
  const { t } = useTranslation()
  const { traceId } = useParams<{ traceId: string }>()
  const navigate = useConsoleNavigate()
  const trace = { ...mockTraceDetail, id: traceId || mockTraceDetail.id }
  const [selected, setSelected] = useState(trace.default_selected)

  const selectedSpan =
    trace.spans.find((span) => span.id === selected && span.detail) ||
    trace.spans.find((span) => span.id === trace.default_selected)

  return (
    <>
      <Backlink to="/v2/observe/traces">{t('console.traceDetail.back')}</Backlink>

      <div className="rd-head">
        <h1>{trace.id}</h1>
        <StatusChip status={trace.status} label={trace.status_label} />
        <span className="chip">
          <i style={{ background: trace.subject_color }} />
          {trace.subject_id}
        </span>
        <span className="spacer" />
        <button
          type="button"
          className="btn"
          onClick={() => navigate(`/v2/observe/runs/${trace.run_id}`)}
        >
          <IconChevronRight />
          {t('console.traceDetail.openRun')}
        </button>
        <button type="button" className="btn">
          <IconExport />
          {t('console.traceDetail.exportOtlp')}
        </button>
      </div>

      <div className="rd-meta">
        {trace.meta.map((item) => (
          <span key={item.key}>
            {item.key}
            <b>
              {'to' in item && item.to ? (
                <a
                  className="runid"
                  href={item.to as string}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(item.to as string)
                  }}
                >
                  {item.value}
                </a>
              ) : (
                item.value
              )}
            </b>
          </span>
        ))}
      </div>

      <div className="rdgrid">
        <WorkbenchPanel
          title={t('console.traceDetail.waterfall')}
          hint={t('console.traceDetail.waterfallHint')}
        >
          <div className="axisrow">
            <span>{t('console.traceDetail.axis.span')}</span>
            <span>{t('console.traceDetail.axis.kind')}</span>
            <span className="ticks">
              {trace.ticks.map((tick) => (
                <span key={tick}>{tick}</span>
              ))}
            </span>
            <span style={{ textAlign: 'right' }}>{t('console.traceDetail.axis.dur')}</span>
          </div>
          <ul className="spans">
            {trace.spans.map((span) => (
              <li
                key={span.id}
                className={cn(span.id === selected && 'sel')}
                onClick={() => setSelected(span.id)}
              >
                <span
                  className={cn('sname', span.child && 'child')}
                  style={{ paddingLeft: span.child ? 42 : span.id === 'span_root' ? 0 : 16 }}
                >
                  {span.expandable && (
                    <span className="twist">
                      <IconChevronRight size={10} />
                    </span>
                  )}
                  {span.bold ? <b>{span.name}</b> : span.name}
                </span>
                <span className="kind" style={{ '--c': span.color } as React.CSSProperties}>
                  <i />
                  {span.kind}
                </span>
                <span className="wf">
                  <i
                    style={{ '--c': span.color, left: `${span.left}%`, width: `${span.width}%` } as React.CSSProperties}
                  />
                </span>
                <span className="sdur">{span.duration}</span>
              </li>
            ))}
          </ul>
          <CodeBlock command={trace.code.command} output={trace.code.output} />
        </WorkbenchPanel>

        <div className="rail">
          <WorkbenchPanel title={t('console.traceDetail.span')} hint={t('console.traceDetail.spanHint')}>
            <ul className="kv">
              {selectedSpan?.detail?.span.map((item) => (
                <li key={item.key}>
                  <span className="k">{item.key}</span>
                  <span className="v" style={item.ok ? { color: 'var(--success-foreground)' } : undefined}>
                    {item.value}
                  </span>
                </li>
              ))}
            </ul>
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.traceDetail.attributes')}>
            <KeyValueList items={selectedSpan?.detail?.attributes || []} />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.traceDetail.spanEvents')}>
            <KeyValueList items={selectedSpan?.detail?.events || []} />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.traceDetail.breakdown')}>
            <div style={{ padding: '12px 14px 4px' }}>
              <TBar slices={trace.breakdown} style={{ width: '100%' }} />
            </div>
            <KeyValueList items={trace.breakdown_rows} />
          </WorkbenchPanel>
        </div>
      </div>
    </>
  )
}
