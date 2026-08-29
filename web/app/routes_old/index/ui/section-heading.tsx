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
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="space-y-3">
        <div className="inline-flex items-center gap-3 rounded-full border border-border/70 bg-panel/78 px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground shadow-[0_8px_18px_rgba(15,23,42,0.05)]">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          {t(eyebrowKey)}
        </div>
        <div className="text-3xl font-semibold tracking-tight text-foreground md:text-[2rem]">
          {t(titleKey)}
        </div>
      </div>
      <div className="max-w-2xl text-sm leading-6 text-muted-foreground">
        {t(descriptionKey)}
      </div>
    </div>
  )
}
