// Document status type.
export type DocumentStatus = 'pending' | 'processing' | 'processed' | 'failed'

// Processing stages for embeddings.
export type ProcessingStage = 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed'

// Processing stats.
export interface ProcessingStats {
  chunks: number
  tokens: number
  vectors: number
}

// Chunk configuration.
export interface ChunkConfig {
  chunkSize: number
  chunkOverlap: number
  separator: string
}

// Chunk model.
export interface Chunk {
  id: string
  documentId: string
  content: string
  tokens: number
  embedding?: number[]
  metadata: {
    startIndex: number
    endIndex: number
    page?: number
  }
  vectorized?: boolean
  indexed?: boolean
  tags?: string[]
}

// Processing details.
export interface ProcessingInfo {
  stage: ProcessingStage
  progress: number
  error: string | null
  stats: ProcessingStats
  chunks: Chunk[]
  config: ChunkConfig
}

// Document model.
export interface Document {
  id: string
  title: string
  type: typeof DocumentType[keyof typeof DocumentType]
  size: string
  status: DocumentStatus
  createdAt: string
  updatedAt: string
  progress: number
  tags: string[]
  versions: Array<{ version: string; date: string }>
  content: string
  processing: ProcessingInfo
}

// Document type enum.
export const DocumentType = {
  TEXT: 'text',
  IMAGE: 'image',
  VIDEO: 'video',
  LINK: 'link',
  WEBSITE: 'website',
} as const

// Segment configuration.
export interface SegmentConfig {
  parent: {
    separator: string
    maxLength: number
  }
  child: {
    separator: string
    maxLength: number
  }
  preprocess: {
    replaceWhitespace: boolean
    removeUrl: boolean
  }
} 
