import request, { type RequestConfigWithToast } from '@/utils/request'

/** The records the ledger exports, in the contract `kernel/specs/v1/ledger_spec`. */
export type LedgerExportKind = 'runs' | 'steps' | 'costs' | 'audit' | 'events'
export type LedgerExportFormat = 'jsonl' | 'csv'

function filenameOf(disposition: unknown, fallback: string): string {
  const match = /filename="?([^";]+)"?/.exec(String(disposition || ''))
  return match?.[1] || fallback
}

function save(data: Blob, filename: string): void {
  const href = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(href)
}

/**
 * Download a run's evidence bundle: a zip of its ledger records and
 * governance evidence with SHA-256 sums, as the server builds it.
 */
export async function downloadRunEvidence(
  runId: string,
): Promise<{ filename: string; sha256: string | null }> {
  const config: RequestConfigWithToast = { responseType: 'blob', suppressErrorToast: true }
  const response = await request.get<Blob>(`/runs/${runId}/evidence`, config)
  const filename = filenameOf(response.headers?.['content-disposition'], `soit-evidence-${runId}.zip`)
  save(response.data, filename)
  return { filename, sha256: (response.headers?.['x-soit-evidence-sha256'] as string) || null }
}

/**
 * Download one kind of ledger record created in [since, until) as a file.
 * Owners and admins only; the server records the export in the audit ledger.
 */
export async function downloadLedgerExport(
  kind: LedgerExportKind,
  params: { since: string; until?: string; format: LedgerExportFormat },
): Promise<string> {
  const config: RequestConfigWithToast = { params, responseType: 'blob', suppressErrorToast: true }
  const response = await request.get<Blob>(`/exports/${kind}`, config)
  const filename = filenameOf(response.headers?.['content-disposition'], `soit-${kind}.${params.format}`)
  save(response.data, filename)
  return filename
}
