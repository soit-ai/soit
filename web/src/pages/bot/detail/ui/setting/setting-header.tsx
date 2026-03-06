import { Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { useTranslation } from '@/i18n'

type SettingHeaderProps = {
  handleSave: () => void
  isSaving: boolean
}

export function SettingHeader({ handleSave, isSaving }: SettingHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-row flex-1 items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">All Inboxes</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>{t('bot.settings.header.title')}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-center gap-2">
        <Button onClick={handleSave} size={'sm'} disabled={isSaving}>
          {isSaving ? (
            <>
              <span className="mr-2 h-4 w-4 animate-spin">⏳</span>
              {t('bot.settings.header.saving')}
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              {t('bot.settings.header.save')}
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
