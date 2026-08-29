import { useTranslation } from '@/i18n'
import { useState, useEffect } from 'react'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Globe, Check } from 'lucide-react'
import { languages } from '@/i18n/language'
import { setLocaleOnClient } from '@/i18n'
import { toast } from '@/components/ui/sonner'
function Page() {
  const { t, i18n } = useTranslation()
  const [currentLanguage, setCurrentLanguage] = useState(i18n.language)
  const [dateFormat, setDateFormat] = useState(localStorage.getItem('dateFormat') || 'YYYY-MM-DD')
  const [timeFormat, setTimeFormat] = useState(localStorage.getItem('timeFormat') || '24')
  const [timezone, setTimezone] = useState(localStorage.getItem('timezone') || 'Asia/Shanghai')
  const [isSaving, setIsSaving] = useState(false)

  // Timezone options.
  const timezones = [
    { value: 'Asia/Shanghai', label: t('system.settings.lang.timezones.shanghai') },
    { value: 'Asia/Tokyo', label: t('system.settings.lang.timezones.tokyo') },
    { value: 'America/New_York', label: t('system.settings.lang.timezones.newYork') },
    { value: 'Europe/London', label: t('system.settings.lang.timezones.london') },
    { value: 'Europe/Paris', label: t('system.settings.lang.timezones.paris') },
  ]

  // Date format options.
  const dateFormats = [
    { value: 'YYYY-MM-DD', label: t('system.settings.lang.dateFormats.iso') },
    { value: 'DD/MM/YYYY', label: t('system.settings.lang.dateFormats.european') },
    { value: 'MM/DD/YYYY', label: t('system.settings.lang.dateFormats.american') },
  ]

  // Handle language changes.
  const handleLanguageChange = (value: string) => {
    setCurrentLanguage(value)
  }

  // Save all settings.
  const handleSaveSettings = async () => {
    try {
      setIsSaving(true)

      // Save language settings.
      await setLocaleOnClient(currentLanguage as any)

      // Persist regional settings to local storage.
      localStorage.setItem('dateFormat', dateFormat)
      localStorage.setItem('timeFormat', timeFormat)
      localStorage.setItem('timezone', timezone)

      // Show success toast.
      toast.success(t('system.settings.lang.saveSuccess'), {
        description: t('system.settings.lang.settingsApplied'),
      })
    } catch (error) {
      console.error('Failed to save settings:', error)
      toast.error(t('system.settings.lang.saveError'), {
        description: t('system.settings.lang.settingsError'),
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">{t('system.settings.lang.languageAndRegion')}</h3>
          <p className="text-sm text-muted-foreground mt-1">{t('system.settings.lang.customizePreferences')}</p>
        </div>
      </div>

      <div className="grid gap-6">
        {/* Language settings */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              <CardTitle>{t('system.settings.lang.languageSettings')}</CardTitle>
            </div>
            <CardDescription>{t('system.settings.lang.selectPreferredLanguage')}</CardDescription>
          </CardHeader>
          <CardContent>
            <RadioGroup
              value={currentLanguage}
              onValueChange={handleLanguageChange}
              className="grid gap-4"
            >
              {languages.map((lang) => (
                <div key={lang.value} className="flex items-center space-x-2">
                  <RadioGroupItem value={lang.value} id={lang.value} />
                  <Label htmlFor={lang.value} className="flex items-center cursor-pointer">
                    <span className="text-base">{lang.name}</span>
                    {currentLanguage === lang.value && (
                      <Check className="ml-2 h-4 w-4 text-primary" />
                    )}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </CardContent>
        </Card>

        {/* Region settings */}
        <Card>
          <CardHeader>
            <CardTitle>{t('system.settings.lang.regionSettings')}</CardTitle>
            <CardDescription>{t('system.settings.lang.customizeDateTimeFormat')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Date format */}
              <div className="space-y-2">
                <Label htmlFor="date-format">{t('system.settings.lang.dateFormat')}</Label>
                <Select value={dateFormat} onValueChange={(value) => value != null && setDateFormat(value)}>
                  <SelectTrigger id="date-format">
                    <SelectValue placeholder={t('system.settings.lang.selectDateFormat')} />
                  </SelectTrigger>
                  <SelectContent>
                    {dateFormats.map((format) => (
                      <SelectItem key={format.value} value={format.value}>
                        {format.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Time format */}
              <div className="space-y-2">
                <Label>{t('system.settings.lang.timeFormat')}</Label>
                <RadioGroup
                  value={timeFormat}
                  onValueChange={setTimeFormat}
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="12" id="12h" />
                    <Label htmlFor="12h">{t('system.settings.lang.hourFormat12')}</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="24" id="24h" />
                    <Label htmlFor="24h">{t('system.settings.lang.hourFormat24')}</Label>
                  </div>
                </RadioGroup>
              </div>
            </div>

            <Separator />

            {/* Timezone settings */}
            <div className="space-y-2">
              <Label htmlFor="timezone">{t('system.settings.lang.timezone')}</Label>
              <Select value={timezone} onValueChange={(value) => value != null && setTimezone(value)}>
                <SelectTrigger id="timezone">
                  <SelectValue placeholder={t('system.settings.lang.selectTimezone')} />
                </SelectTrigger>
                <SelectContent>
                  {timezones.map((tz) => (
                    <SelectItem key={tz.value} value={tz.value}>
                      {tz.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end">
            <Button onClick={handleSaveSettings} disabled={isSaving}>
              {isSaving ? t('common.saving' as any) : t('common.save' as any)}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}

export default Page
