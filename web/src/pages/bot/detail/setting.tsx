import { useTranslation } from '@/i18n'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Save } from 'lucide-react'
import { BasicInfo } from '@/pages/bot/detail/ui/setting/basic-info'
import { StyleSettings } from '@/pages/bot/detail/ui/setting/style-settings'
import { PermissionsSettings } from '@/pages/bot/detail/ui/setting/permissions-settings'
import { AdvancedSettings } from '@/pages/bot/detail/ui/setting/advanced-settings'
import { ConversationSettings } from '@/pages/bot/detail/ui/setting/conversation-settings'
import { useNavLayout } from '@/components/layout/nav-layout'
import { SettingHeader } from './ui/setting/setting-header'

function Page() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState('basic')
  const [isSaving, setIsSaving] = useState(false)
  const { setHeaderContent } = useNavLayout()

  // Set header content.
  useEffect(() => {
    setHeaderContent(<SettingHeader handleSave={handleSave} isSaving={isSaving} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  // Mock bot profile data.
  const [botInfo, setBotInfo] = useState({
    name: 'Support Assistant',
    description: 'An AI support bot that answers product questions and handles common customer requests.',
    avatar: '/avatars/bot-1.png',
    category: 'customer-service',
    language: 'en-US',
    visibility: 'team',
    tags: ['Support', 'Product Q&A', 'Auto-reply']
  })

  // Simulate saving settings.
  const handleSave = () => {
    setIsSaving(true)
    // Simulate the save operation.
    setTimeout(() => {
      setIsSaving(false)
      // Success feedback can be added here.
    }, 1000)
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Tabs defaultValue="basic" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
          <TabsList className="w-full md:w-auto grid grid-cols-4 md:flex">
            <TabsTrigger value="basic">{t('bot.settings.tabs.basic')}</TabsTrigger>
            <TabsTrigger value="style">{t('bot.settings.tabs.style')}</TabsTrigger>
            <TabsTrigger value="permissions">{t('bot.settings.tabs.permissions')}</TabsTrigger>
            <TabsTrigger value="advanced">{t('bot.settings.tabs.advanced')}</TabsTrigger>
          </TabsList>
          
          {/* Reserve space on the right for future filters or search. */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            <Button variant="outline" size="sm" onClick={() => setActiveTab("basic")}>
              {t('bot.settings.reset')}
            </Button>
          </div>
        </div>

        <TabsContent value="basic" className="mt-4 space-y-4">
          <BasicInfo botInfo={botInfo} setBotInfo={setBotInfo} />
          <ConversationSettings />
        </TabsContent>

        <TabsContent value="style" className="mt-4 space-y-4">
          <StyleSettings botInfo={botInfo} />
        </TabsContent>

        <TabsContent value="permissions" className="mt-4 space-y-4">
          <PermissionsSettings />
        </TabsContent>

        <TabsContent value="advanced" className="mt-4 space-y-4">
          <AdvancedSettings />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
