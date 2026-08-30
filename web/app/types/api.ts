export type ApiEnvelope<T> = {
  success: true
  code: string
  message: string
  data: T
  request_id?: string
  run_id?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
  has_next?: boolean
  /**
   * Rows matching the same filters, ignoring pagination. Only present when the
   * caller passed `with_total`, so `undefined` means "not asked for" — never
   * an empty result set.
   */
  total?: number | null
}
