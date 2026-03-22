import React, { useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'

interface DialogOptions {
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  onConfirm?: () => void
  onCancel?: () => void
}

export function useDialog() {
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState<DialogOptions>({
    title: '',
    description: '',
    confirmText: '确认',
    cancelText: '取消'
  })

  const DialogComponent = useCallback(() => {
    return createPortal(
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{options.title}</DialogTitle>
            <DialogDescription>{options.description}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                options.onCancel?.()
                setOpen(false)
              }}
            >
              {options.cancelText}
            </Button>
            <Button
              onClick={() => {
                options.onConfirm?.()
                setOpen(false)
              }}
            >
              {options.confirmText}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>,
      document.body
    )
  }, [open, options])

  const confirm = useCallback((newOptions: DialogOptions) => {
    setOptions({
      ...options,
      ...newOptions,
      confirmText: newOptions.confirmText || '确认',
      cancelText: newOptions.cancelText || '取消'
    })
    setOpen(true)
    return DialogComponent
  }, [options, DialogComponent])

  const alert = useCallback((newOptions: Omit<DialogOptions, 'cancelText' | 'onCancel'>) => {
    setOptions({
      ...options,
      ...newOptions,
      confirmText: newOptions.confirmText || '确认'
    })
    setOpen(true)
    return DialogComponent
  }, [options, DialogComponent])

  return {
    confirm,
    alert,
    DialogComponent
  }
}

export default useDialog
