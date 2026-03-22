import { useTranslation } from '@/i18n'
import { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/hooks/use-toast'
import { User, Mail, Phone, Briefcase, LayoutDashboard } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getCurrentUser, updateCurrentUser } from '@/services/identity-service'
import { useQuery } from '@/hooks/use-query'

function Page() {
  const { t } = useTranslation()

  const { data: currentUser } = useQuery({
    queryKey: ['current-user'],
    queryFn: () => getCurrentUser(),
  })

  // User profile defaults.
  const [user, setUser] = useState({
    name: t('system.settings.account.defaults.name'),
    email: 'zhangsan@example.com',
    avatar: '',
    phone: '',
    role: t('system.settings.account.defaults.role'),
    company: '',
    title: '',
    bio: '',
  })

  useEffect(() => {
    if (!currentUser) {
      return
    }
    const profile = currentUser.profile || {}
    setUser({
      name: currentUser.name || t('system.settings.account.defaults.name'),
      email: currentUser.email || 'zhangsan@example.com',
      avatar: profile.avatar || '',
      phone: profile.phone || '',
      role: currentUser.workspace_role || currentUser.tenant_role || t('system.settings.account.defaults.role'),
      company: profile.company || '',
      title: profile.title || '',
      bio: profile.bio || '',
    })
  }, [currentUser, t])
  
  // Handle form input changes.
  const handleInputChange = (field: string, value: string | boolean) => {
    setUser(prev => ({
      ...prev,
      [field]: value
    }))
  }
  
  // Save profile changes.
  const handleSaveProfile = () => {
    updateCurrentUser({
      name: user.name,
      email: user.email,
      profile: {
        avatar: user.avatar,
        phone: user.phone,
        company: user.company,
        title: user.title,
        bio: user.bio,
      },
    })
      .then(() => {
        toast({
          title: t('system.settings.account.toast.savedTitle'),
          description: t('system.settings.account.toast.savedDescription'),
        })
      })
      .catch(() => {})
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">{t('system.settings.account.title')}</h3>
          <p className="text-sm text-muted-foreground mt-1">{t('system.settings.account.description')}</p>
        </div>
      </div>

      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="profile">{t('system.settings.account.tabs.profile')}</TabsTrigger>
          <TabsTrigger value="status">{t('system.settings.account.tabs.status')}</TabsTrigger>
        </TabsList>
        
        {/* Profile tab */}
        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>{t('system.settings.account.profile.title')}</CardTitle>
              <CardDescription>{t('system.settings.account.profile.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex flex-col md:flex-row gap-6">
                <div className="flex flex-col items-center gap-4">
                  <Avatar className="h-24 w-24">
                    <AvatarImage src={user.avatar || ''} />
                    <AvatarFallback className="text-2xl">{user.name.charAt(0)}</AvatarFallback>
                  </Avatar>
                  <Button variant="outline" size="sm">{t('system.settings.account.profile.changeAvatar')}</Button>
                </div>
                <div className="flex-1 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">{t('system.settings.account.fields.name')}</Label>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <Input 
                          id="name" 
                          value={user.name} 
                          onChange={(e) => handleInputChange('name', e.target.value)} 
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">{t('system.settings.account.fields.email')}</Label>
                      <div className="flex items-center gap-2">
                        <Mail className="h-4 w-4 text-muted-foreground" />
                        <Input 
                          id="email" 
                          type="email" 
                          value={user.email} 
                          onChange={(e) => handleInputChange('email', e.target.value)} 
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="phone">{t('system.settings.account.fields.phone')}</Label>
                      <div className="flex items-center gap-2">
                        <Phone className="h-4 w-4 text-muted-foreground" />
                        <Input 
                          id="phone" 
                          value={user.phone} 
                          onChange={(e) => handleInputChange('phone', e.target.value)} 
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="role">{t('system.settings.account.fields.role')}</Label>
                      <Input 
                        id="role" 
                        value={user.role} 
                        disabled 
                      />
                    </div>
                  </div>
                  
                  <Separator className="my-4" />
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="company">{t('system.settings.account.fields.company')}</Label>
                      <div className="flex items-center gap-2">
                        <Briefcase className="h-4 w-4 text-muted-foreground" />
                        <Input 
                          id="company" 
                          value={user.company} 
                          onChange={(e) => handleInputChange('company', e.target.value)} 
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="title">{t('system.settings.account.fields.title')}</Label>
                      <div className="flex items-center gap-2">
                        <LayoutDashboard className="h-4 w-4 text-muted-foreground" />
                        <Input 
                          id="title" 
                          value={user.title} 
                          onChange={(e) => handleInputChange('title', e.target.value)} 
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="bio">{t('system.settings.account.fields.bio')}</Label>
                    <Input 
                      id="bio" 
                      value={user.bio} 
                      onChange={(e) => handleInputChange('bio', e.target.value)} 
                    />
                  </div>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button onClick={handleSaveProfile}>{t('system.settings.account.actions.save')}</Button>
            </CardFooter>
          </Card>
        </TabsContent>

      </Tabs>
    </div>
  )
}

export default Page
