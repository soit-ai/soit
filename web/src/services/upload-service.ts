import { get, post } from '@/utils/request'

export const siteInfo = (): Promise<any> => {
  return get(`/site/info`)
}

export const siteConfig = (): Promise<any> => {
  return get(`/site/config`)
}

// Upload local file
export const uploadLocalFile = (file: File, sceneId?: string, sceneType?: string): Promise<any> => {
  const formData = new FormData()
  formData.append('file', file)
  if (sceneId) formData.append('scene_id', sceneId)
  if (sceneType) formData.append('scene_type', sceneType)
  return post('/upload/add', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// Upload remote file
export const uploadRemoteFile = (url: string, sceneId?: string, sceneType?: string): Promise<any> => {
  return post('/upload/remote', {
    url,
    scene_id: sceneId,
    scene_type: sceneType
  })
}

// Get file content
export const getFile = (fileId: string): Promise<Blob> => {
  return get(`/files/${fileId}`, {
    responseType: 'blob'
  })
}

// Delete file
export const deleteFile = (fileId: string): Promise<any> => {
  return post(`/files/${fileId}/delete`)
}

// Batch delete files
export const batchDeleteFiles = (fileIds: string[]): Promise<any> => {
  return post('/files/batch-delete', {
    file_ids: fileIds
  })
}
