import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'

export function ModelSettings() {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.settings.model.title')}</CardTitle>
        <CardDescription>{t('bot.settings.model.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="temperature">{t('bot.settings.model.temperature')}</Label>
            <div className="flex items-center gap-2">
              <Input
                id="temperature"
                type="range"
                min="0"
                max="1"
                step="0.1"
                defaultValue="0.7"
                className="w-full"
              />
              <span className="w-8 text-center">0.7</span>
            </div>
            <p className="text-xs text-muted-foreground">{t('bot.settings.model.temperatureHint')}</p>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="max-tokens">{t('bot.settings.model.maxTokens')}</Label>
            <Select defaultValue="1024">
              <SelectTrigger id="max-tokens">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="512">512</SelectItem>
                <SelectItem value="1024">1024</SelectItem>
                <SelectItem value="2048">2048</SelectItem>
                <SelectItem value="4096">4096</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="system-prompt">{t('bot.settings.model.systemPrompt')}</Label>
          <Textarea
            id="system-prompt"
            placeholder={t('bot.settings.model.systemPromptPlaceholder')}
            className="min-h-[100px]"
            defaultValue={t('bot.settings.model.systemPromptDefault')}
          />
        </div>
        
        <Separator />
        
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.model.toggles.functionCalling.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.model.toggles.functionCalling.description')}</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.model.toggles.knowledge.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.model.toggles.knowledge.description')}</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">{t('bot.settings.model.toggles.streaming.title')}</Label>
              <p className="text-sm text-muted-foreground">{t('bot.settings.model.toggles.streaming.description')}</p>
            </div>
            <Switch checked={true} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
