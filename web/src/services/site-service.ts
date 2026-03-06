import { get, post } from '@/utils/request'

export const siteInfo = (): Promise<any> => {
  return get(`/site/info`)
}

export const siteConfig = (): Promise<any> => {
  return get(`/site/config`)
}
