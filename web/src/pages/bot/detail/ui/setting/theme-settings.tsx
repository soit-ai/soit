import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { useTranslation } from '@/i18n'

export function ThemeSettings() {
  const { t } = useTranslation()
  const themeColors = [
    { color: '#0ea5e9', labelKey: 'bot.settings.theme.colors.blue' },
    { color: '#10b981', labelKey: 'bot.settings.theme.colors.green' },
    { color: '#f59e0b', labelKey: 'bot.settings.theme.colors.yellow' },
    { color: '#ef4444', labelKey: 'bot.settings.theme.colors.red' },
    { color: '#8b5cf6', labelKey: 'bot.settings.theme.colors.purple' },
    { color: '#ec4899', labelKey: 'bot.settings.theme.colors.pink' },
    { color: '#6b7280', labelKey: 'bot.settings.theme.colors.gray' },
    { color: '#000000', labelKey: 'bot.settings.theme.colors.black' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('bot.settings.theme.title')}</CardTitle>
        <CardDescription>{t('bot.settings.theme.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>{t('bot.settings.theme.primaryColor')}</Label>
          <div className="flex flex-wrap gap-2">
            {themeColors.map((theme, index) => (
              <Button 
                key={index}
                variant="outline" 
                className={`h-8 w-8 rounded-full p-0 ${index === 0 ? 'ring-2 ring-offset-2' : ''}`}
                style={{ backgroundColor: theme.color }}
                title={t(theme.labelKey)}
              />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t('bot.settings.theme.primaryColorTip')}</p>
        </div>
        
        <div className="space-y-2">
          <Label>{t('bot.settings.theme.appearance')}</Label>
          <div className="grid grid-cols-3 gap-4">
            <div className="overflow-hidden rounded-lg border p-2">
              <div className="flex flex-col items-center gap-2">
                <div className="h-20 w-full rounded-md bg-blue-50"></div>
                <p className="text-sm font-medium">{t('bot.settings.theme.modes.light')}</p>
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{t('bot.settings.theme.modes.current')}</Badge>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border p-2">
              <div className="flex flex-col items-center gap-2">
                <div className="h-20 w-full rounded-md bg-gray-900"></div>
                <p className="text-sm font-medium">{t('bot.settings.theme.modes.dark')}</p>
                <Button size="sm" variant="outline" className="h-7 w-full text-xs">{t('bot.settings.theme.modes.select')}</Button>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border p-2">
              <div className="flex flex-col items-center gap-2">
                <div className="h-20 w-full rounded-md bg-gradient-to-r from-blue-500 to-purple-500"></div>
                <p className="text-sm font-medium">{t('bot.settings.theme.modes.gradient')}</p>
                <Button size="sm" variant="outline" className="h-7 w-full text-xs">{t('bot.settings.theme.modes.select')}</Button>
              </div>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="border-radius">{t('bot.settings.theme.borderRadius')}</Label>
            <div className="flex items-center gap-2">
              <Input
                id="border-radius"
                type="range"
                min="0"
                max="20"
                step="1"
                defaultValue="8"
                className="w-full"
              />
              <span className="w-8 text-center">{t('bot.settings.theme.pxValue', { value: 8 })}</span>
            </div>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="animation-speed">{t('bot.settings.theme.animationSpeed')}</Label>
            <Select defaultValue="normal">
              <SelectTrigger id="animation-speed">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="slow">{t('bot.settings.theme.animation.slow')}</SelectItem>
                <SelectItem value="normal">{t('bot.settings.theme.animation.normal')}</SelectItem>
                <SelectItem value="fast">{t('bot.settings.theme.animation.fast')}</SelectItem>
                <SelectItem value="none">{t('bot.settings.theme.animation.none')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
