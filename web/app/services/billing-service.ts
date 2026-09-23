import { get, post } from '@/utils/request'
/**
 * Mirrors `CreditBalanceResponse`. Credits are the ledger's own unit, so the
 * balance carries no currency; `deducted_total` is signed (zero or negative).
 */
export interface CreditBalance {
  balance: string
  granted_total: string
  deducted_total: string
  entry_count: number
  status: 'ok' | 'low' | 'exhausted' | string
  enforcement_enabled: boolean
  low_balance_threshold: string
}

export type CreditEntryKind = 'grant' | 'deduction' | 'adjustment' | string

/** Mirrors `CreditLedgerEntryResponse`: one signed credit movement. */
export interface CreditEntry {
  id: string
  tenant_id: string
  workspace_id: string
  kind: CreditEntryKind
  credits_delta: string
  cost_entry_id?: string | null
  run_id?: string | null
  /** The spend a deduction converted from, when it came from a cost entry. */
  currency?: string | null
  amount?: string | null
  note?: string | null
  created_by: string
  created_at: string
}

export const getCreditBalance = (): Promise<CreditBalance> => {
  return get<CreditBalance>('/billing/credits/balance')
}

export const listCreditEntries = (params?: {
  kind?: CreditEntryKind
  run_id?: string
  limit?: number
  offset?: number
}): Promise<CreditEntry[]> => {
  return get<CreditEntry[]>('/billing/credits/entries', params)
}

export const grantCredits = (data: { credits: string; note?: string }): Promise<CreditEntry> => {
  return post<CreditEntry>('/billing/credits/grants', data)
}
