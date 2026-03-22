import * as React from 'react'
import { Link as LinkBase, type LinkProps} from 'react-router'
import { cn } from "@/lib/utils"

// @ts-ignore
export const Link = React.forwardRef((props: LinkProps, ref) => {
  const { to, ..._props } = props as LinkProps
  const search = new URLSearchParams(window.location.search)
  let _to = to
  if (search.get('nosider')) {
    // Automatically splice nosider, judge whether there is a?, if there is, splice &, if not, splice?
    if (typeof _to === 'string') {
      _to += _to.includes('?') ? '&nosider=true' : '?nosider=true'
    }
  }

  return <LinkBase to={_to} {..._props} className={cn('cursor-pointer', props?.className)} />
})
