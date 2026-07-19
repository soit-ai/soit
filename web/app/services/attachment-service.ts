import type { ApiEnvelope } from '@/types/api'
import { API_BASE_URL, buildAuthHeaders } from '@/utils/request'

export type GovernedAttachment = {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  checksum: string
  status: string
  thread_id?: string | null
  created_at: string
  updated_at: string
}

export const attachmentContentUrl = (attachmentId: string): string => {
  const path = `${API_BASE_URL}/attachments/${encodeURIComponent(attachmentId)}/content`
  return new URL(path, globalThis.location?.origin || 'http://localhost').toString()
}

export const governedContentRequestUrl = (url: string): URL => {
  const pageOrigin = globalThis.location?.origin || 'http://localhost'
  const apiBase = new URL(API_BASE_URL, pageOrigin)
  const candidate = new URL(url, apiBase.origin)
  if (candidate.origin !== apiBase.origin) {
    throw new Error('Governed file URL must use the configured API origin')
  }
  const basePath = apiBase.pathname.replace(/\/$/, '')
  const relativePath = candidate.pathname.slice(basePath.length)
  const isAttachment = /^\/attachments\/[^/]+\/content$/.test(relativePath)
  const isArtifact = /^\/runs\/[^/]+\/artifacts\/[^/]+\/content$/.test(relativePath)
  if (!candidate.pathname.startsWith(`${basePath}/`) || (!isAttachment && !isArtifact)) {
    throw new Error('Governed file URL is outside the approved content routes')
  }
  return candidate
}

export const fetchGovernedContent = (
  url: string,
  signal?: AbortSignal
): Promise<Response> => {
  return fetch(governedContentRequestUrl(url), {
    headers: buildAuthHeaders(),
    signal,
  })
}

export const uploadAttachment = async (file: File): Promise<GovernedAttachment> => {
  const body = new FormData()
  body.append('file', file, file.name)
  const response = await fetch(`${API_BASE_URL}/attachments`, {
    method: 'POST',
    headers: buildAuthHeaders(),
    body,
  })
  const payload = (await response.json().catch(() => null)) as
    | ApiEnvelope<GovernedAttachment>
    | { message?: string; data?: GovernedAttachment }
    | null
  if (!response.ok || !payload?.data) {
    throw new Error(payload?.message || `Attachment upload failed with HTTP ${response.status}`)
  }
  return payload.data
}

export const downloadGovernedFile = async (url: string, filename: string): Promise<void> => {
  const response = await fetchGovernedContent(url)
  if (!response.ok) {
    throw new Error(`Artifact download failed with HTTP ${response.status}`)
  }
  const objectUrl = URL.createObjectURL(await response.blob())
  try {
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    link.click()
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}
