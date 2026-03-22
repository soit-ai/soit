import { useCallback } from 'react'
import { useNavigate as _useNavigate, useSearchParams as _useSearchParams, type NavigateOptions, type To } from 'react-router'

export const useNavigate = () => {
  const navigate = _useNavigate()
  const [searchParams] = _useSearchParams()
  
  return useCallback(
    (to: To | number, options?: NavigateOptions) => {
      if (typeof to === 'number') {
        console.log('useNavigate to', to)
        navigate(to.toString() as To, options)
        return
      }

      let nextTo: To = to
      if (to && searchParams.get('nosider')) {
        if (typeof to === 'string') {
          nextTo = to + (to.includes('?') ? '&nosider=true' : '?nosider=true')
        } else {
          const mergedParams = new URLSearchParams(to.search ?? '')
          mergedParams.set('nosider', 'true')
          nextTo = { ...to, search: mergedParams.toString() }
        }
      }
      console.log('useNavigate nextTo', nextTo)
      navigate(nextTo, options)
    },
    [navigate, searchParams],
  )
}

export const useWindowOpen = () => {
  const [searchParams] = _useSearchParams()
  
  return (url: string, target?: string, features?: string) => {
    let _url = url
    if (searchParams.get('nosider')) {
      _url = _url + (_url.includes('?') ? '&nosider=true' : '?nosider=true')
    }
    return window.open(_url, target, features)
  }
}
