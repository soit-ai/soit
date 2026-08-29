import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleToggle,
  IconPlus,
  Pager,
  StatusChip,
  Workbench,
  WorkbenchPanel,
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
import { mockSchedules } from '../../mocks/execute'
import { useTranslation } from '@/i18n'

// BACKEND-PENDING: schedules are the one screen with no server side at all —
// there is no schedule model, service or route anywhere in the backend, so this
// is a design surface for a feature that has not been built. Every other
// console screen now reads its real service; these rows are fixtures and must
// not be mistaken for live state.
export default function ConsoleSchedules() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(mockSchedules.map((row) => [row.id, row.enabled])),
  )

  return (
    <Workbench
      title={t('console.schedules.title')}
      description={t('console.schedules.description')}
      actions={
        <ConsoleButton variant="primary">
          <IconPlus />
          {t('console.schedules.newSchedule')}
        </ConsoleButton>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.schedules.columns.schedule')}</TableHead>
              <TableHead>{t('console.schedules.columns.cron')}</TableHead>
              <TableHead>{t('console.schedules.columns.target')}</TableHead>
              <TableHead className="num">{t('console.schedules.columns.nextFire')}</TableHead>
              <TableHead>{t('console.schedules.columns.lastOutcome')}</TableHead>
              <TableHead>{t('console.schedules.columns.enabled')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {mockSchedules.map((row) => (
              <TableRow key={row.id} className="rowlink">
                <TableCell>
                  <b style={{ fontWeight: 600 }}>{row.name}</b>
                  <br />
                  <span className="dimmer" style={{ fontSize: 11 }}>
                    {row.note}
                  </span>
                </TableCell>
                <TableCell className="mono dim">{row.cron}</TableCell>
                <TableCell>
                  <span className="idm" style={{ '--c': row.target_color } as React.CSSProperties}>
                    <i />
                    {row.target}
                  </span>
                </TableCell>
                <TableCell className="num dim">{row.next_fire}</TableCell>
                <TableCell>
                  {row.outcome_run ? (
                    <a
                      className="runid"
                      href={`/observe/runs/${row.outcome_run}`}
                      onClick={(event) => {
                        event.preventDefault()
                        navigate(`/observe/runs/${row.outcome_run}`)
                      }}
                    >
                      {row.outcome_run}
                    </a>
                  ) : (
                    <span className="mono dimmer">{row.outcome_note}</span>
                  )}{' '}
                  <StatusChip status={row.outcome_status} label={row.outcome_label} />
                </TableCell>
                <TableCell>
                  <ConsoleToggle
                    on={enabled[row.id]}
                    label={`${row.name} ${enabled[row.id] ? 'enabled' : 'disabled'}`}
                    onChange={(next) => setEnabled((state) => ({ ...state, [row.id]: next }))}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pager summary={t('console.schedules.pagerNote')} />
      </WorkbenchPanel>
    </Workbench>
  )
}
