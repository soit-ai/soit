import { toast } from 'sonner'
import { fetchEventSource, type FetchEventSourceInit } from '@microsoft/fetch-event-source'
import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { uuidv4 } from './uuid'

const TIME_OUT = 100000
const BASE_URL = (import.meta.env.VITE_BASE_URL || '/api/v1').replace(/\/$/, '')
export const API_BASE_URL = BASE_URL
const ERROR_CODES_OK = new Set([0, 200])
const ERROR_CODES_UNAUTHORIZED = new Set(['unauthorized', 'forbidden', "UNAUTHORIZED", "FORBIDDEN"])
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
// Add request interceptors
request.interceptors.request.use(
  // @ts-ignore
  function (config) {
    // console.log('request.use config', config);
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
    // console.log('request.use newConfig', newConfig);
    return newConfig
  },
  function (error) {
    console.log('Request ErrorHandler error:', error)
    let _key = uuidv4()
    let msg =
      error?.response?.data?.message ||
      error?.response?.data?.msg ||
      error?.response?.data?.detail ||
      error?.message ||
      'Response ErrorHandler Error'
    toast.error(msg, { id: _key, richColors: true, closeButton: true, position: 'top-center' })
    return Promise.reject(error)
  }
)

const resolveResponseError = (data: any): string | null => {
  if (!data || typeof data !== 'object') {
    return null
  }
  if (data.success === false) {
    return data.message || data.msg || data.detail || 'Request failed'
  }
  if (typeof data.code === 'number' && !ERROR_CODES_OK.has(data.code)) {
    return data.message || data.msg || data.detail || `Request failed with code ${data.code}`
  }
  if (data.error) {
    if (typeof data.error === 'string') {
      return data.error
    }
    if (typeof data.error === 'object' && data.error.message) {
      return data.error.message
    }
  }
  return null
}

request.interceptors.response.use(
  async function (response: any) {
    console.log('response.use res', response)
    const msg = resolveResponseError(response?.data)
    if (msg) {
      let _key = uuidv4()
      isUnauthorizedError(response?.data?.code) && (_key = 'nologin_notice')
      console.log('response.use msg', msg, _key)
      toast.error(msg, { id: _key, richColors: true, closeButton: true, position: 'top-center' })
      return Promise.reject(new Error(msg))
    }
    return Promise.resolve(response)
  },
  function (error) {
    console.log('Response ErrorHandler error:', error, error?.response?.data)
    let _key = uuidv4()
    let msg =
      error?.response?.data?.message ||
      error?.response?.data?.msg ||
      error?.response?.data?.detail ||
      error?.message ||
      'Response ErrorHandler Error'
    isUnauthorizedError(error?.response?.data?.code) && (_key = 'nologin_notice')
    console.log('Response ErrorHandler error:', error, msg, _key)
    toast.error(msg, { id: _key, richColors: true, closeButton: true, position: 'top-center' })
    return Promise.reject(error)
  }
)

function isUnauthorizedError(code: number | string): boolean {
  if (ERROR_CODES_UNAUTHORIZED.has(code.toString().toLowerCase())) {
    console.log('isUnauthorizedError', code)
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
    console.log('post error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// get http
export async function get<T = any>(url: string, params?: Record<string, any>, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.get(url, { params, ...config })
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    console.log('get error:', error, url, params, config)
    return Promise.reject(error)
  }
}

// put http
export async function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.put(url, data, config)
    // console.log('PUT res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('put error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// delete http
export async function del<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.delete(url, { params: data, ...config })
    // console.log('DELETE res:', res, url);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('delete error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// patch http
export async function patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> {
  try {
    const res = await request.patch(url, data, config)
    // console.log('PATCH res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('patch error:', error, url, data, config)
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
    // console.log('POST res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('postForm error:', error, url, data, config)
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
    // console.log('POST res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('getForm error:', error, url, params, config)
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
    // console.log('POST res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('getExportFile error:', error, url, params, config)
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
    // console.log('POST res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('postExportFile error:', error, url, data, config)
    return Promise.reject(error)
  }
}

// upload file
export const uploadFile = async <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T, any>> => {
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
    // console.log('POST res:', res, url, data);
    return Promise.resolve(res.data) as Promise<AxiosResponse<T, any>>
  } catch (error) {
    // throw new Error(error);
    console.log('uploadFile error:', error, url, data, config)
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
    // console.log('POST res:', res, url, data);
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
    console.log('downloadFile error:', error, url, params, config)
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
    console.log('fetchEventSource start')
    // listen abortSignal
    config?.signal?.addEventListener('abort', () => {
      console.log('fetchEventSource abort')
      end = true
      resolveQueue?.(null)
    })
    fetchEventSource(url, {
      method: 'POST',
      headers: {
        'Content-Type': ContentType.json,
        ...config?.headers,
      },
      openWhenHidden: true,
      signal: config?.signal,
      body: JSON.stringify(data),
      async onopen(response) {
        console.log('fetchEventSource onopen:', response)
        if (response.ok) {
          return
        } else {
          throw new Error('fetchEventSource onopen error')
        }
      },
      onmessage(event) {
        console.log('fetchEventSource onmessage:', event.data)
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
        console.log('fetchEventSource onclose')
        end = true
        Promise.resolve().then(() => {
          resolveQueue?.(null)
        })
      },
      onerror(err) {
        console.log('fetchEventSource onerror:', err)
        error = err
        end = true
        Promise.resolve().then(() => {
          resolveQueue?.(null)
        })
        throw err
      },
    })
    // console.log('POST res:', res, url, data);
    while (true) {
      if (error) {
        console.log('fetchEventSource error')
        throw new Error(error)
        break
      }
      if (end) {
        console.log('fetchEventSource end')
        break
      }
      if (eventQueue.length > 0) {
        yield await eventQueue.shift()
      } else {
        yield await new Promise((resolve) => (resolveQueue = resolve))
      }
    }
  } catch (error) {
    // throw new Error(error);
    console.log('sse error:', error, url, data, config)
    return Promise.reject(error)
  }
}
