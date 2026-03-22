"use client"

import { toast as sonnerToast } from "sonner"

type ToastProps = {
  title?: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  type?: 'normal' | 'action' | 'success' | 'info' | 'warning' | 'error' | 'loading' | 'default'
}

export function toast({ title, description, action, type = 'default' }: ToastProps) {
  switch (type) {
    case 'default':
      return sonnerToast(title, {
        description,
        action,
      })
    case 'error':
      return sonnerToast.error(title, {
        description,
        action,
      })
    case 'success':
      return sonnerToast.success(title, {
        description,
        action,
      })
    case 'info':
      return sonnerToast.info(title, {
        description,
        action,
      })
    case 'warning':
      return sonnerToast.warning(title, {
        description,
        action,
      })
    case 'loading':
      return sonnerToast.loading(title, {
        description,
        action,
      })
    case 'normal':
      return sonnerToast(title, {
        description,
        action,
      })
    case 'action':
      return sonnerToast(title, {
        description,
        action,
      })
  }
  return sonnerToast(title, {
    description,
    action,
  })
}

export function useToast() {
  return {
    toast,
    dismiss: sonnerToast.dismiss,
  }
}
