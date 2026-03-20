import { useMemo } from 'react'

import { useTranslation } from '@/i18n'

export function useHomeFormatters() {
  const { i18n } = useTranslation()

  const numberFormatter = useMemo(
    () =>
      new Intl.NumberFormat(i18n.language, {
        maximumFractionDigits: 0,
      }),
    [i18n.language]
  )

  const compactFormatter = useMemo(
    () =>
      new Intl.NumberFormat(i18n.language, {
        notation: 'compact',
        maximumFractionDigits: 1,
      }),
    [i18n.language]
  )

  return {
    formatNumber: (value: number) => numberFormatter.format(value),
    formatCompact: (value: number) => compactFormatter.format(value),
  }
}
