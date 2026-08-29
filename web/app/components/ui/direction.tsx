"use client"

import * as React from "react"
import {
  DirectionProvider as DirectionProviderPrimitive,
  useDirection,
  type TextDirection,
} from "@base-ui/react/direction-provider"

function DirectionProvider({
  dir,
  direction,
  children,
}: {
  dir?: TextDirection
  direction?: TextDirection
  children?: React.ReactNode
}) {
  return (
    <DirectionProviderPrimitive direction={direction ?? dir}>
      {children}
    </DirectionProviderPrimitive>
  )
}

export { DirectionProvider, useDirection }
