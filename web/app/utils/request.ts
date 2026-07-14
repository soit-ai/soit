import { toast } from 'sonner'
import { fetchEventSource, type FetchEventSourceInit } from '@microsoft/fetch-event-source'
import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { debugLog } from './debug'
import { uuidv4 } from './uuid'

const TIME_OUT = 100000
const BASE_URL = (import.meta.env.VITE_BASE_URL || '/api/v1').replace(/\/$/, '')
export const API_BASE_URL = BASE_URL
const ERROR_CODES_OK = new Set([0, 200])
const ERROR_CODES_UNAUTHORIZED = new Set(['unauthorized', 'forbidden', 'UNAUTHORIZED', 'FORBIDDEN'])
const AUTO_REDIRECT_UNAUTHORIZED = true

export const ContentType = {
  json: 'application/json',
  stream: 'text/event-stream',
  audio: 'audio/mpeg',
  form: 'application/x-www-form-urlencoded; charset=UTF-8',
  download: 'application/octet-stream', // for download
  downloadZip: 'application/zip', // for download
  upload: 'multipart/form-data', // for upload
}

// Create request instance
const request = axios.create({
  baseURL: BASE_URL,
  timeout: TIME_OUT,
})

export type RequestConfigWithToast = AxiosRequestConfig & {
  suppressErrorToast?: boolean
}
// Add request interceptors
request.interceptors.request.use(
  // @ts-ignore
  function (config) {
    const token = localStorage.getItem('token') || ''
    const headers = {
      'Content-Type': ContentType.json,
      ...(config?.headers as Record<string, string> | undefined),
    } as Record<string, string>
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    const workspaceId = localStorage.getItem('workspace_id') || ''
    if (workspaceId) {
      headers['X-Workspace-Id'] = workspaceId
    }
    const newConfig = { ...config, headers } as AxiosRequestConfig
    return newConfig
  },
  function (error) {
    debugLog('Request ErrorHandler error:', error)
    let _key = uuidv4()
    let msg = error?.response?.data?.message || error?.message || 'Response ErrorHandler Error'
    toast.error(msg, { id: _key, richColors: true, closeButton: true, position: 'top-center' })
    return Promise.reject(error)
  }
)

const resolveResponseError = (data: any): string | null => {
  if (!data || typeof data !== 'object') {
    return null
  }
  if (data.success === false) {
    return data.message || 'Request failed'
  }
  if (typeof data.code === 'number' && !ERROR_CODES_OK.has(data.code)) {
    return data.message || `Request failed with code ${data.code}`
  }
  return null
}

request.interceptors.response.use(
  async function (response: any) {
    debugLog('response.use res', response)
    const msg = resolveResponseError(response?.data)
    if (msg) {
      let _key = uuidv4()
      isUnauthorizedError(response?.data?.code) && (_key = 'nologin_notice')
      debugLog('response.use msg', msg, _key)
      const suppressErrorToast = Boolean((response?.config as RequestConfigWithToast | undefined)?.suppressErrorToast)
      if (!suppressErrorToast) {
        toast.error(msg, { id: _key, richColors: true, closeButton: true, position: 'top-center' })
      }
      return Promise.reject(new Error(msg))
    }
    return Promise.resolve(response)
  },
  function (error) {
    debugLog('Response ErrorHandler error:', error, error?.response?.data)
    let _key = uuidv4()
    let msg = error?.response?.data?.message || error?.message || 'Response ErrorHandler Error'
    isUnauthorizedError(error?.response?.data?.code) && (_key = 'nologin_notice')
    debugLog('Response ErrorHandler resolved message:', msg, _key)
    const suppressErrorToast = Boolean((error?.config as RequestConfigWithToast | undefined)?.suppressErrorToast)
    if (!suppressErrorToast) {
      toast.error(msg, { id: _key, richColors: true, closeButton: true, position: 'top-center' })
    }
    return Promise.reject(error)
  }
)

function isUnauthorizedError(code: number | string | null | undefined): boolean {
  if (code === null || code === undefined) {
    return false
  }
  if (ERROR_CODES_UNAUTHORIZED.has(code.toString().toLowerCase())) {
    debugLog('isUnauthorizedError', code)
    if (AUTO_REDIRECT_UNAUTHORIZED) {
      setTimeout(() => {
        // Preserve current URL.
        let url = encodeURIComponent(window.location.href)
        // Redirect with return URL.
        window.location.href = `/sign-in?redirect=${url}`
      }, 1000)
    }
    return true
  }
  return false
}

export default request

// post http
export async function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.post(url, data, config)
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    debugLog('post error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// get http
export async function get<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.get(url, { params, ...config })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    debugLog('get error:', error, url, params, config)
    return Promise.reject(error)
  }
}

// put http
export async function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.put(url, data, config)
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('put error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// delete http
export async function del<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.delete(url, { params: data, ...config })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('delete error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// patch http
export async function patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.patch(url, data, config)
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('patch error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// post form
export async function postForm<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request({
      url: url,
      data: data,
      method: 'POST',
      ...config,
      headers: {
        'Content-Type': ContentType.form,
        ...config?.headers,
      },
    })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('postForm error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// get form
export async function getForm<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request({
      url: url,
      params: params,
      method: 'GET',
      ...config,
      headers: {
        'Content-Type': ContentType.form,
        ...config?.headers,
      },
    })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('getForm error:', error, url, params, config)
    return Promise.reject(error)
  }
}

// get file
export const getFile = async <T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> => {
  try {
    const res = await request({
      url: url,
      params: params,
      method: 'GET',
      responseType: 'blob',
      ...config,
      headers: {
        'Content-Type': ContentType.download,
        ...config?.headers,
      },
    })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('getExportFile error:', error, url, params, config)
    return Promise.reject(error)
  }
}

// post file
export const postFile = async <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> => {
  try {
    const res = await request({
      url: url,
      data: data,
      method: 'POST',
      responseType: 'blob',
      ...config,
      headers: {
        'Content-Type': ContentType.download,
        ...config?.headers,
      },
    })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('postExportFile error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// upload file
export const uploadFile = async <T = any>(url: string, data?: any, config?: RequestConfigWithToast): Promise<AxiosResponse<T, any>> => {
  try {
    const res = await request({
      url: url,
      data: data,
      method: 'POST',
      ...config,
      headers: {
        'Content-Type': ContentType.upload,
        ...config?.headers,
      },
    })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('uploadFile error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// download file
export const downloadFile = async <T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> => {
  try {
    const res = await request({
      url: url,
      params: params,
      method: 'GET',
      responseType: 'blob',
      ...config,
      headers: {
        'Content-Type': ContentType.download,
        ...config?.headers,
      },
    })
    if (res.status !== 200) {
      throw new Error('downloadFile error')
    }
    const downloadUrl = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = res.headers['content-disposition']
    a.click()
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    debugLog('downloadFile error:', error, url, params, config)
    return Promise.reject(error)
  }
}

// sse http
export type SseEvent = {
  event: string
  data: string
}

export async function* sse(url: string, data?: any, config?: FetchEventSourceInit): AsyncGenerator<SseEvent, void, any> {
  try {
    const eventQueue: any[] = []
    let end = false
    let error = null
    let resolveQueue: ((value: any) => void) | null = null
    debugLog('fetchEventSource start')
    // listen abortSignal
    config?.signal?.addEventListener('abort', () => {
      debugLog('fetchEventSource abort')
      end = true
      resolveQueue?.(null)
    })
    const sourcePromise = fetchEventSource(url, {
      method: 'POST',
      headers: {
        'Content-Type': ContentType.json,
        ...config?.headers,
      },
      openWhenHidden: true,
      signal: config?.signal,
      body: JSON.stringify(data),
      async onopen(response) {
        debugLog('fetchEventSource onopen:', response)
        if (response.ok) {
          return
        } else {
          throw new Error('fetchEventSource onopen error')
        }
      },
      onmessage(event) {
        debugLog('fetchEventSource onmessage:', event.data)
        const _res = {
          event: event.event || 'message',
          data: event.data,
        }
        if (resolveQueue) {
          resolveQueue(_res)
          resolveQueue = null
        } else {
          eventQueue.push(_res)
        }
      },
      onclose() {
        debugLog('fetchEventSource onclose')
        end = true
        Promise.resolve().then(() => {
          resolveQueue?.(null)
        })
      },
      onerror(err) {
        debugLog('fetchEventSource onerror:', err)
        error = err
        end = true
        Promise.resolve().then(() => {
          resolveQueue?.(null)
        })
        throw err
      },
    }).catch((err) => {
      debugLog('fetchEventSource rejected:', err)
      error = err
      end = true
      Promise.resolve().then(() => {
        resolveQueue?.(null)
      })
    })
    while (true) {
      if (error) {
        debugLog('fetchEventSource error')
        throw new Error(error)
        break
      }
      if (eventQueue.length > 0) {
        yield await eventQueue.shift()
      } else if (end) {
        debugLog('fetchEventSource end')
        break
      } else {
        yield await new Promise((resolve) => (resolveQueue = resolve))
      }
    }
    await sourcePromise
  } catch (error) {
    debugLog('sse error:', error, url, data, config)
    throw error
  }
}
