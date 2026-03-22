import { useTranslation } from '@/i18n'
import { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { toast } from '@/hooks/use-toast'
import { Shield, Key, Smartphone, History, Bell, Lock, LogOut, AlertTriangle } from 'lucide-react'
import { changePassword, getCurrentUser, updateCurrentUser } from '@/services/identity-service'
import { useQuery } from '@/hooks/use-query'
function Page() {
  const { t } = useTranslation()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false)
  const [showQRCode, setShowQRCode] = useState(false)
  const [verificationCode, setVerificationCode] = useState('')
  const [notifyUnusualActivity, setNotifyUnusualActivity] = useState(true)
  const [notifyPasswordChange, setNotifyPasswordChange] = useState(true)
  const [notifyNewLogin, setNotifyNewLogin] = useState(true)
  const { data: currentUser } = useQuery({
    queryKey: ['current-user'],
    queryFn: () => getCurrentUser(),
  })

  useEffect(() => {
    if (!currentUser?.profile) {
      return
    }
    const security = currentUser.profile.security || {}
    setTwoFactorEnabled(Boolean(security.two_factor_enabled))
    setNotifyUnusualActivity(security.notify_unusual_activity ?? true)
    setNotifyPasswordChange(security.notify_password_change ?? true)
    setNotifyNewLogin(security.notify_new_login ?? true)
  }, [currentUser])

  const buildSecurityProfile = (overrides: Record<string, any> = {}) => ({
    two_factor_enabled: twoFactorEnabled,
    notify_unusual_activity: notifyUnusualActivity,
    notify_password_change: notifyPasswordChange,
    notify_new_login: notifyNewLogin,
    ...overrides,
  })

  // Login history list.
  const loginHistory = [
    { id: 1, device: 'Chrome / Windows', location: t('system.settings.security.sessions.locations.beijing'), ip: '114.88.xxx.xxx', time: '2025-05-30 14:23', status: 'success' },
    { id: 2, device: 'Safari / macOS', location: t('system.settings.security.sessions.locations.shanghai'), ip: '180.167.xxx.xxx', time: '2025-05-28 09:15', status: 'success' },
    { id: 3, device: 'Firefox / Linux', location: t('system.settings.security.sessions.locations.london'), ip: '82.132.xxx.xxx', time: '2025-05-25 22:45', status: 'suspicious' },
    { id: 4, device: 'Mobile App / iOS', location: t('system.settings.security.sessions.locations.guangzhou'), ip: '113.108.xxx.xxx', time: '2025-05-20 16:30', status: 'success' },
    { id: 5, device: 'Unknown', location: t('system.settings.security.sessions.locations.moscow'), ip: '213.87.xxx.xxx', time: '2025-05-18 03:12', status: 'blocked' },
  ]

  // Handle password changes.
  const handleChangePassword = () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast({
        title: t('system.settings.security.toast.errorTitle'),
        description: t('system.settings.security.toast.fillAllFields'),
        type: 'error'
      })
      return
    }

    if (newPassword !== confirmPassword) {
      toast({
        title: t('system.settings.security.toast.errorTitle'),
        description: t('system.settings.security.toast.passwordMismatch'),
        type: 'error'
      })
      return
    }

    changePassword({ current_password: currentPassword, new_password: newPassword })
      .then(() => {
        toast({
          title: t('system.settings.security.toast.successTitle'),
          description: t('system.settings.security.toast.passwordUpdated'),
        })
        // Clear form fields.
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
      })
      .catch(() => {})
  }

  // Handle two-factor enable/disable.
  const handleToggleTwoFactor = () => {
    if (!twoFactorEnabled) {
      // Enable two-factor.
      setShowQRCode(true)
    } else {
      // Disable two-factor.
      setShowQRCode(false)
      updateCurrentUser({
        profile: {
          security: buildSecurityProfile({ two_factor_enabled: false }),
        },
      })
        .then(() => {
          setTwoFactorEnabled(false)
          toast({
            title: t('system.settings.security.toast.disabledTitle'),
            description: t('system.settings.security.toast.twoFactorDisabled'),
          })
        })
        .catch(() => {})
    }
  }

  // Handle verification code confirmation.
  const handleVerifyCode = () => {
    if (!verificationCode || verificationCode.length !== 6) {
      toast({
        title: t('system.settings.security.toast.errorTitle'),
        description: t('system.settings.security.toast.invalidCode'),
        type: 'error'
      })
      return
    }

    updateCurrentUser({
      profile: {
        security: buildSecurityProfile({
          two_factor_enabled: true,
          two_factor_verified_at: new Date().toISOString(),
        }),
      },
    })
      .then(() => {
        setTwoFactorEnabled(true)
        setShowQRCode(false)
        setVerificationCode('')
        toast({
          title: t('system.settings.security.toast.successTitle'),
          description: t('system.settings.security.toast.twoFactorEnabled'),
        })
      })
      .catch(() => {})
  }

  // Handle logout from other sessions.
  const handleLogoutOtherSessions = () => {
    updateCurrentUser({
      profile: {
        security: buildSecurityProfile({
          logout_others_at: new Date().toISOString(),
        }),
      },
    })
      .then(() => {
        toast({
          title: t('system.settings.security.toast.successTitle'),
          description: t('system.settings.security.toast.sessionsLoggedOut'),
        })
      })
      .catch(() => {})
  }

  const handleSaveNotifications = () => {
    updateCurrentUser({
      profile: {
        security: buildSecurityProfile(),
      },
    })
      .then(() => {
        toast({
          title: t('system.settings.security.toast.successTitle'),
          description: t('system.settings.security.notifications.description'),
        })
      })
      .catch(() => {})
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">{t('system.settings.security.title')}</h3>
          <p className="text-sm text-muted-foreground mt-1">{t('system.settings.security.description')}</p>
        </div>
      </div>

      <Tabs defaultValue="password" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="password">{t('system.settings.security.tabs.password')}</TabsTrigger>
          <TabsTrigger value="2fa">{t('system.settings.security.tabs.twoFactor')}</TabsTrigger>
          <TabsTrigger value="sessions">{t('system.settings.security.tabs.sessions')}</TabsTrigger>
          <TabsTrigger value="notifications">{t('system.settings.security.tabs.notifications')}</TabsTrigger>
        </TabsList>
        
        {/* Password tab */}
        <TabsContent value="password">
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
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder={t('system.settings.security.password.currentPlaceholder')}
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="new-password">{t('system.settings.security.password.new')}</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder={t('system.settings.security.password.newPlaceholder')}
                />
                <p className="text-xs text-muted-foreground">
                  {t('system.settings.security.password.hint')}
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="confirm-password">{t('system.settings.security.password.confirm')}</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder={t('system.settings.security.password.confirmPlaceholder')}
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button onClick={handleChangePassword}>{t('system.settings.security.password.submit')}</Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        {/* Two-factor tab */}
        <TabsContent value="2fa">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.security.twoFactor.title')}</CardTitle>
              <CardDescription>{t('system.settings.security.twoFactor.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <div className="font-medium">{t('system.settings.security.twoFactor.toggleTitle')}</div>
                  <div className="text-sm text-muted-foreground">
                    {t('system.settings.security.twoFactor.toggleDescription')}
                  </div>
                </div>
                <Switch
                  checked={twoFactorEnabled}
                  onCheckedChange={handleToggleTwoFactor}
                />
              </div>
              
              {showQRCode && (
                <div className="space-y-4 p-4 border rounded-md">
                  <div className="text-center">
                    <p className="mb-2">{t('system.settings.security.twoFactor.qrPrompt')}</p>
                    <div className="bg-gray-200 w-48 h-48 mx-auto mb-4 flex items-center justify-center">
                      <p className="text-xs text-gray-500">{t('system.settings.security.twoFactor.qrPlaceholder')}</p>
                    </div>
                    <p className="text-sm text-muted-foreground mb-4">
                      {t('system.settings.security.twoFactor.manualKeyLabel')}{' '}
                      <span className="font-mono">ABCD EFGH IJKL MNOP</span>
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="verification-code">{t('system.settings.security.twoFactor.codeLabel')}</Label>
                    <Input
                      id="verification-code"
                      value={verificationCode}
                      onChange={(e) => setVerificationCode(e.target.value)}
                      placeholder={t('system.settings.security.twoFactor.codePlaceholder')}
                      maxLength={6}
                    />
                  </div>
                  
                  <Button onClick={handleVerifyCode}>{t('system.settings.security.twoFactor.verify')}</Button>
                </div>
              )}
              
              {twoFactorEnabled && (
                <Alert>
                  <Shield className="h-4 w-4" />
                  <AlertTitle>{t('system.settings.security.twoFactor.enabledTitle')}</AlertTitle>
                  <AlertDescription>
                    {t('system.settings.security.twoFactor.enabledDescription')}
                  </AlertDescription>
                </Alert>
              )}
              
              {twoFactorEnabled && (
                <div className="space-y-2">
                  <h3 className="font-medium">{t('system.settings.security.twoFactor.recovery.title')}</h3>
                  <p className="text-sm text-muted-foreground">
                    {t('system.settings.security.twoFactor.recovery.description')}
                  </p>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div className="font-mono text-sm bg-muted p-2 rounded">ABCDEF-123456</div>
                    <div className="font-mono text-sm bg-muted p-2 rounded">GHIJKL-789012</div>
                    <div className="font-mono text-sm bg-muted p-2 rounded">MNOPQR-345678</div>
                    <div className="font-mono text-sm bg-muted p-2 rounded">STUVWX-901234</div>
                  </div>
                  <Button variant="outline" className="mt-2">{t('system.settings.security.twoFactor.recovery.download')}</Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Sessions tab */}
        <TabsContent value="sessions">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{t('system.settings.security.sessions.title')}</CardTitle>
                  <CardDescription>{t('system.settings.security.sessions.description')}</CardDescription>
                </div>
                <Button variant="outline" onClick={handleLogoutOtherSessions}>
                  <LogOut className="mr-2 h-4 w-4" />
                  {t('system.settings.security.sessions.logoutOthers')}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {loginHistory.map((session) => (
                  <div key={session.id} className="flex items-center justify-between p-4 border rounded-md">
                    <div className="space-y-1">
                      <div className="font-medium">{session.device}</div>
                      <div className="text-sm text-muted-foreground">
                        {t('system.settings.security.sessions.locationWithIp', {
                          location: session.location,
                          ip: session.ip,
                        })}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {session.time}
                      </div>
                    </div>
                    <div>
                      {session.status === 'success' && (
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                          {t('system.settings.security.sessions.status.success')}
                        </Badge>
                      )}
                      {session.status === 'suspicious' && (
                        <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
                          <AlertTriangle className="mr-1 h-3 w-3" />
                          {t('system.settings.security.sessions.status.suspicious')}
                        </Badge>
                      )}
                      {session.status === 'blocked' && (
                        <Badge variant="destructive">
                          {t('system.settings.security.sessions.status.blocked')}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Security notifications tab */}
        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.security.notifications.title')}</CardTitle>
              <CardDescription>{t('system.settings.security.notifications.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <div className="font-medium">{t('system.settings.security.notifications.unusual.title')}</div>
                  <div className="text-sm text-muted-foreground">
                    {t('system.settings.security.notifications.unusual.description')}
                  </div>
                </div>
                <Switch
                  checked={notifyUnusualActivity}
                  onCheckedChange={setNotifyUnusualActivity}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <div className="font-medium">{t('system.settings.security.notifications.password.title')}</div>
                  <div className="text-sm text-muted-foreground">
                    {t('system.settings.security.notifications.password.description')}
                  </div>
                </div>
                <Switch
                  checked={notifyPasswordChange}
                  onCheckedChange={setNotifyPasswordChange}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <div className="font-medium">{t('system.settings.security.notifications.newLogin.title')}</div>
                  <div className="text-sm text-muted-foreground">
                    {t('system.settings.security.notifications.newLogin.description')}
                  </div>
                </div>
                <Switch
                  checked={notifyNewLogin}
                  onCheckedChange={setNotifyNewLogin}
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button onClick={handleSaveNotifications}>{t('system.settings.security.notifications.save')}</Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
