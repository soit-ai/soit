export { Backlink } from './backlink'
export { CodeBlock } from './code-block'
export { ConsoleButton } from './button'
export { DataStateNote, DataStateRow, useDataStateLabel, type DataStateProps } from './data-state'
export { EmptyState } from './empty-state'
export { FilterChip, FilterSearch, Seg } from './filters'
export { Hist } from './hist'
export { IdBadge } from './id-badge'
export { ConsoleModal, type ConsoleModalProps } from './modal'
export { KeyValueList, type KeyValueItem } from './kv'
export { KindChip, CONSOLE_KIND_COLOR, type ConsoleKind } from './kind-chip'
export { Pager } from './pager'
export { PagePlaceholder } from './page-placeholder'
export { StatTile, StatTileGrid, type StatTileDelta } from './stat-tile'
export { TaskProgress } from './task-progress'
export { ConsoleToggle } from './toggle'
export { StatusChip, CONSOLE_STATUS_TONE, runStatusToConsole, type ConsoleStatus } from './status-chip'
export { ConsoleTabs, type ConsoleTabItem } from './tabs'
export {
  TBar,
  TBarLegend,
  BREAKDOWN_COLOR,
  type BreakdownKind,
  type BreakdownSlice,
} from './tbar'
export { Workbench, WorkbenchPanel } from './workbench'
export * from './icons'

// Data-heavy building blocks reused from the shared Box suite (referenced,
// not copied — the legacy tree keeps using the same source).
export { BoxDataTable, BoxPagination, MetricStrip } from '@/components/box'
export type { BoxDataTableColumn, MetricStripItem } from '@/components/box'
