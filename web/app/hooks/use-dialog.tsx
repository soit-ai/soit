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
import { useTranslation } from '@/i18n'

interface DialogOptions {
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  onConfirm?: () => void
  onCancel?: () => void
}

export function useDialog() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState<DialogOptions>({
    title: '',
    description: '',
    confirmText: t('common.operation.confirm'),
    cancelText: t('common.operation.cancel')
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
      confirmText: newOptions.confirmText || t('common.operation.confirm'),
      cancelText: newOptions.cancelText || t('common.operation.cancel')
    })
    setOpen(true)
    return DialogComponent
  }, [options, DialogComponent, t])

  const alert = useCallback((newOptions: Omit<DialogOptions, 'cancelText' | 'onCancel'>) => {
    setOptions({
      ...options,
      ...newOptions,
      confirmText: newOptions.confirmText || t('common.operation.confirm')
    })
    setOpen(true)
    return DialogComponent
  }, [options, DialogComponent, t])

  return {
    confirm,
    alert,
    DialogComponent
  }
}

export default useDialog
