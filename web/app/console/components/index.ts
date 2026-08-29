export { ConsoleButton } from './button'
export { EmptyState } from './empty-state'
export { IdBadge } from './id-badge'
export { KindChip, CONSOLE_KIND_COLOR, type ConsoleKind } from './kind-chip'
export { StatTile, StatTileGrid, type StatTileDelta } from './stat-tile'
export { StatusChip, CONSOLE_STATUS_TONE, type ConsoleStatus } from './status-chip'
export { Workbench, WorkbenchPanel } from './workbench'

// Data-heavy building blocks reused from the shared Box suite (referenced,
// not copied — the legacy tree keeps using the same source).
export { BoxDataTable, BoxPagination, MetricStrip } from '@/components/box'
export type { BoxDataTableColumn, MetricStripItem } from '@/components/box'
