import { get, post } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface CreditBalance {
  currency: string
  balance: string
  granted_total?: string | null
  consumed_total?: string | null
  updated_at?: string | null
}

export type CreditEntryKind = 'grant' | 'consumption' | 'adjustment' | string

export interface CreditEntry {
  id: string
  tenant_id: string
  workspace_id?: string | null
  kind: CreditEntryKind
  currency: string
  amount: string
  balance_after?: string | null
  source_ref?: string | null
  run_id?: string | null
  note?: string | null
  created_by?: string | null
  created_at: string
}

export const getCreditBalance = (): Promise<CreditBalance> => {
  return get<CreditBalance>('/billing/credits/balance')
}

export const listCreditEntries = (params?: {
  kind?: CreditEntryKind
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<CreditEntry>> => {
  return get<PaginatedResponse<CreditEntry>>('/billing/credits/entries', params)
}

export const grantCredits = (data: {
  currency: string
  amount: string
  note?: string
}): Promise<CreditEntry> => {
  return post<CreditEntry>('/billing/credits/grants', data)
}
