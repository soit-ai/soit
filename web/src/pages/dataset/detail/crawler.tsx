import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
function Page() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-1 flex-col gap-4">
      <Label>{t('dataset.crawler.title')}</Label>
    </div>
  )
}

export default Page
