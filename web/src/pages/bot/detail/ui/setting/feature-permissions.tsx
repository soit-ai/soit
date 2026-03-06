import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { useTranslation } from '@/i18n'

export function FeaturePermissions() {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.settings.permissions.title')}</CardTitle>
        <CardDescription>{t('bot.settings.permissions.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.permissions.items.fileUpload.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.permissions.items.fileUpload.description')}</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.permissions.items.externalTools.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.permissions.items.externalTools.description')}</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.permissions.items.codeExecution.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.permissions.items.codeExecution.description')}</p>
            </div>
            <Switch checked={false} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.permissions.items.webSearch.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.permissions.items.webSearch.description')}</p>
            </div>
            <Switch checked={true} />
          </div>
        </div>
        
        <Separator />
        
        <div className="space-y-2">
          <Label>{t('bot.settings.permissions.limits.title')}</Label>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="daily-limit">{t('bot.settings.permissions.limits.dailyLimit')}</Label>
              <Select defaultValue="100">
                <SelectTrigger id="daily-limit">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="50">{t('bot.settings.permissions.limits.dailyOptions.fifty')}</SelectItem>
                  <SelectItem value="100">{t('bot.settings.permissions.limits.dailyOptions.oneHundred')}</SelectItem>
                  <SelectItem value="500">{t('bot.settings.permissions.limits.dailyOptions.fiveHundred')}</SelectItem>
                  <SelectItem value="unlimited">{t('bot.settings.permissions.limits.dailyOptions.unlimited')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="token-limit">{t('bot.settings.permissions.limits.tokenLimit')}</Label>
              <Select defaultValue="4000">
                <SelectTrigger id="token-limit">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="2000">{t('bot.settings.permissions.limits.tokenOptions.twoThousand')}</SelectItem>
                  <SelectItem value="4000">{t('bot.settings.permissions.limits.tokenOptions.fourThousand')}</SelectItem>
                  <SelectItem value="8000">{t('bot.settings.permissions.limits.tokenOptions.eightThousand')}</SelectItem>
                  <SelectItem value="16000">{t('bot.settings.permissions.limits.tokenOptions.sixteenThousand')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
