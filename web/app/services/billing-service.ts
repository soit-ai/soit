import { del, get, patch, post, type RequestConfigWithToast } from '@/utils/request'

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

export type BudgetScope = 'workspace' | 'api_key' | 'user' | 'agent'
export type BudgetPeriod = 'day' | 'month'

/** Mirrors `BudgetResponse`. Amounts are decimal strings in `currency`. */
export interface Budget {
  id: string
  name: string
  scope_kind: BudgetScope | string
  /** Null for a workspace budget; the key, user, principal or agent otherwise. */
  scope_id?: string | null
  period: BudgetPeriod | string
  amount: string
  currency: string
  /** Percentages that notify workspace admins once per period when crossed. */
  thresholds: number[]
  /** A hard stop refuses model and tool calls once the budget is spent. */
  hard_stop: boolean
  status: 'active' | 'disabled' | string
  created_by: string
  created_at: string
  updated_at: string
}

/** Mirrors `BudgetStatusResponse`: where a budget stands in its current period. */
export interface BudgetStatus {
  budget: Budget
  period_start: string
  resets_at: string
  spent: string
  remaining: string
  percent: string
  /** Spend projected to the end of the period at the rate so far. */
  forecast: string
}

export interface BudgetCreate {
  name: string
  scope_kind: BudgetScope
  scope_id?: string
  period: BudgetPeriod
  amount: string
  currency: string
  thresholds: number[]
  hard_stop: boolean
}

export const listBudgetStatuses = (config?: RequestConfigWithToast): Promise<BudgetStatus[]> => {
  return get<BudgetStatus[]>('/billing/budgets/statuses', undefined, config)
}

export const createBudget = (
  data: BudgetCreate,
  config?: RequestConfigWithToast,
): Promise<Budget> => {
  return post<Budget>('/billing/budgets', data, config)
}

/** Scope, period and currency are fixed once a budget exists. */
export const updateBudget = (
  budgetId: string,
  data: {
    name?: string
    amount?: string
    thresholds?: number[]
    hard_stop?: boolean
    status?: 'active' | 'disabled'
  },
  config?: RequestConfigWithToast,
): Promise<Budget> => {
  return patch<Budget>(`/billing/budgets/${budgetId}`, data, config)
}

export const deleteBudget = (budgetId: string, config?: RequestConfigWithToast): Promise<void> => {
  return del(`/billing/budgets/${budgetId}`, undefined, config)
}
