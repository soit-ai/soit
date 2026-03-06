import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { useTranslation } from '@/i18n'

export function IntegrationSettings() {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.settings.integration.title')}</CardTitle>
        <CardDescription>{t('bot.settings.integration.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="api-key">{t('bot.settings.integration.apiKeyLabel')}</Label>
          <div className="flex items-center gap-2">
            <Input
              id="api-key"
              type="password"
              value="sk_bot_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              readOnly
              className="font-mono"
            />
            <Button variant="outline" size="icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-copy"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c0-1.1.9-2 2-2h2"/><path d="M4 12c0-1.1.9-2 2-2h2"/><path d="M4 8c0-1.1.9-2 2-2h2"/></svg>
            </Button>
            <Button variant="outline" size="sm">
              {t('common.operation.reset')}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">{t('bot.settings.integration.apiKeyHint')}</p>
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="webhook-url">{t('bot.settings.integration.webhookLabel')}</Label>
          <Input
            id="webhook-url"
            placeholder="https://example.com/webhook"
          />
          <p className="text-xs text-muted-foreground">{t('bot.settings.integration.webhookHint')}</p>
        </div>
        
        <Separator />
        
        <div className="space-y-2">
          <Label>{t('bot.settings.integration.optionsTitle')}</Label>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-base">{t('bot.settings.integration.slack.title')}</Label>
                <p className="text-sm text-muted-foreground">{t('bot.settings.integration.slack.description')}</p>
              </div>
              <Button variant="outline" size="sm">
                {t('bot.settings.integration.configure')}
              </Button>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-base">{t('bot.settings.integration.embed.title')}</Label>
                <p className="text-sm text-muted-foreground">{t('bot.settings.integration.embed.description')}</p>
              </div>
              <Button variant="outline" size="sm">
                {t('bot.settings.integration.getCode')}
              </Button>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-base">{t('bot.settings.integration.rest.title')}</Label>
                <p className="text-sm text-muted-foreground">{t('bot.settings.integration.rest.description')}</p>
              </div>
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">{t('bot.settings.integration.enabled')}</Badge>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
