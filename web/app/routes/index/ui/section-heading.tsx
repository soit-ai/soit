import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'

type SectionHeadingProps = {
  eyebrowKey: TranslationKey
  titleKey: TranslationKey
  descriptionKey: TranslationKey
}

export function SectionHeading({ eyebrowKey, titleKey, descriptionKey }: SectionHeadingProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="h-px w-10 bg-slate-300 dark:bg-slate-700" />
          <div className="text-[11px] font-medium uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">
            {t(eyebrowKey)}
          </div>
        </div>
        <div className="text-2xl font-semibold tracking-tight text-slate-950 dark:text-slate-50 md:text-[1.9rem]">
          {t(titleKey)}
        </div>
      </div>
      <div className="max-w-2xl text-sm leading-6 text-muted-foreground">
        {t(descriptionKey)}
      </div>
    </div>
  )
}
