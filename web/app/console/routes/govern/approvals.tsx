import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  Pager,
  StatTile,
  StatTileGrid,
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
import { mockApprovalTiles, mockApprovalsDecided, mockApprovalsPending } from '../../mocks/govern'
import { useTranslation } from '@/i18n'

// BACKEND-PENDING: the observe approvals API (+ resolve) exists server-side;
// this screen is new UI over it — fixtures until the wiring pass.
export default function ConsoleApprovals() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<'pending' | 'decided'>('pending')

  return (
    <Workbench
      title={t('console.approvals.title')}
      description={t('console.approvals.description')}
      actions={<ConsoleButton>{t('console.approvals.notificationRules')}</ConsoleButton>}
      tiles={
        <StatTileGrid>
          <StatTile label={t('console.approvals.tiles.pending')} value={mockApprovalTiles.pending.value} sub={<span className="mono dimmer">{mockApprovalTiles.pending.sub}</span>} />
          <StatTile label={t('console.approvals.tiles.decided')} value={mockApprovalTiles.decided.value} sub={<span className="mono dimmer">{mockApprovalTiles.decided.sub}</span>} />
          <StatTile label={t('console.approvals.tiles.median')} value={mockApprovalTiles.median.value} sub={<span className="mono dimmer">{mockApprovalTiles.median.sub}</span>} />
          <StatTile label={t('console.approvals.tiles.escalations')} value={mockApprovalTiles.escalations.value} sub={<span className="mono dimmer">{mockApprovalTiles.escalations.sub}</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'pending', label: t('console.approvals.tabs.pending'), count: 2 },
            { id: 'decided', label: t('console.approvals.tabs.decided'), count: 41 },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
    >
      {tab === 'pending' ? (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.approvals.columns.request')}</TableHead>
                <TableHead>{t('console.approvals.columns.gate')}</TableHead>
                <TableHead>{t('console.approvals.columns.requestedBy')}</TableHead>
                <TableHead className="num">{t('console.approvals.columns.waiting')}</TableHead>
                <TableHead>{t('console.approvals.columns.context')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockApprovalsPending.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <b style={{ fontWeight: 600 }}>{row.request}</b>
                    <br />
                    <span className="dimmer" style={{ fontSize: 11 }}>
                      {row.note}
                    </span>
                  </TableCell>
                  <TableCell className="mono dim">{row.gate}</TableCell>
                  <TableCell className="dim">{row.requested_by}</TableCell>
                  <TableCell
                    className="num"
                    style={row.waiting_warn ? { color: 'var(--warning-foreground)' } : undefined}
                  >
                    {row.waiting}
                  </TableCell>
                  <TableCell>
                    {row.context.map((item, index) => (
                      <span key={item.label}>
                        {index > 0 && ' · '}
                        <a
                          className="runid"
                          href={item.to}
                          onClick={(event) => {
                            event.preventDefault()
                            navigate(item.to)
                          }}
                        >
                          {item.label}
                        </a>
                      </span>
                    ))}
                  </TableCell>
                  <TableCell className="num">
                    <span style={{ display: 'inline-flex', gap: 6 }}>
                      <ConsoleButton variant="primary" size="sm">
                        {t('console.approvals.approve')}
                      </ConsoleButton>
                      <ConsoleButton size="sm">{t('console.approvals.reject')}</ConsoleButton>
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.approvals.pendingNote')} />
        </WorkbenchPanel>
      ) : (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.approvals.columns.time')}</TableHead>
                <TableHead>{t('console.approvals.columns.request')}</TableHead>
                <TableHead>{t('console.approvals.columns.gate')}</TableHead>
                <TableHead>{t('console.approvals.columns.decidedBy')}</TableHead>
                <TableHead className="num">{t('console.approvals.columns.took')}</TableHead>
                <TableHead>{t('console.approvals.columns.decision')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockApprovalsDecided.map((row) => (
                <TableRow key={row.time}>
                  <TableCell className="num dimmer">{row.time}</TableCell>
                  <TableCell className="dim">{row.request}</TableCell>
                  <TableCell className="mono dim">{row.gate}</TableCell>
                  <TableCell className="dim">{row.decided_by}</TableCell>
                  <TableCell className="num dim">{row.took}</TableCell>
                  <TableCell>
                    <StatusChip status={row.status} label={row.status_label} />
                    {row.note && (
                      <>
                        {' '}
                        <span className="dimmer" style={{ fontSize: 10.5 }}>
                          {row.note}
                        </span>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.approvals.decidedNote')} />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
