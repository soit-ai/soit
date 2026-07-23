import { useState } from 'react'
import { ShieldAlert } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useTranslation } from '@/i18n'
import { changePassword } from '@/services/identity-service'
import { toast } from '@/hooks/use-toast'

function Page() {
  const { t } = useTranslation()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast({
        title: t('system.settings.security.toast.errorTitle'),
        description: t('system.settings.security.toast.fillAllFields'),
        type: 'error',
      })
      return
    }
    if (newPassword !== confirmPassword) {
      toast({
        title: t('system.settings.security.toast.errorTitle'),
        description: t('system.settings.security.toast.passwordMismatch'),
        type: 'error',
      })
      return
    }

    setIsSaving(true)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast({
        title: t('system.settings.security.toast.successTitle'),
        description: t('system.settings.security.toast.passwordUpdated'),
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h3 className="text-lg font-bold tracking-tight">{t('system.settings.security.title')}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t('system.settings.security.description')}</p>
      </div>

      <Alert>
        <ShieldAlert className="h-4 w-4" />
        <AlertTitle>Community 1.0 security scope</AlertTitle>
        <AlertDescription>
          TOTP, recovery codes, login-session history, and remote session revocation are not available in this release. No session or recovery data is simulated.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>{t('system.settings.security.password.title')}</CardTitle>
          <CardDescription>{t('system.settings.security.password.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current-password">{t('system.settings.security.password.current')}</Label>
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-password">{t('system.settings.security.password.new')}</Label>
            <Input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">{t('system.settings.security.password.confirm')}</Label>
            <Input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button disabled={isSaving} onClick={() => void handleChangePassword()}>
            {t('system.settings.security.password.submit')}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}

export default Page
