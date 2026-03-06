export type PageTokenPayload = {
  offset: number
  limit: number
}

const encodeBase64 = (value: string) => {
  if (typeof btoa === 'function') {
    return btoa(value)
  }
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(value, 'utf-8').toString('base64')
  }
  throw new Error('Base64 encoder is not available in this environment.')
}

export const encodePageToken = (payload: PageTokenPayload): string => {
  const json = JSON.stringify(payload)
  return encodeBase64(json)
}

export const buildOffsetToken = (page?: number, pageSize?: number): string | undefined => {
  const safePage = page && page > 0 ? page : 1
  const safeSize = pageSize && pageSize > 0 ? pageSize : 20
  const offset = (safePage - 1) * safeSize
  if (offset <= 0) {
    return undefined
  }
  return encodePageToken({ offset, limit: safeSize })
}
