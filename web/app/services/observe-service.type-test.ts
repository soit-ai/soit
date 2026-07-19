import type { DashboardSection } from './observe-service'

export function assertObserveChartNarrowing(section: DashboardSection): void {
  if (section.id === 'tool_reliability') {
    const count: number = section.charts.error_distribution[0]?.count ?? 0
    void count
    // @ts-expect-error Tool reliability charts do not contain health distribution.
    void section.charts.health_distribution
  }
}
