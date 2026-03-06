import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useTranslation } from '@/i18n'

interface DocumentHeaderProps {
  activeTab: string
  onTabChange: (value: string) => void
  documentTypeCounts: {
    all: number
    document: number
    image: number
    video: number
    website: number
    knowledge: number
  }
}

export function DocumentHeader({
  activeTab,
  onTabChange,
  documentTypeCounts,
}: DocumentHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col gap-4">
      
      <Tabs value={activeTab} onValueChange={onTabChange} className="w-full">
        <TabsList className="w-full max-w-2xl grid grid-cols-6">
          <TabsTrigger value="all">
            {t('dataset.document.tabs.all')} <Badge variant="outline" className="ml-1">{documentTypeCounts.all}</Badge>
          </TabsTrigger>
          <TabsTrigger value="document">
            {t('dataset.document.tabs.document')} <Badge variant="outline" className="ml-1">{documentTypeCounts.document}</Badge>
          </TabsTrigger>
          <TabsTrigger value="image">
            {t('dataset.document.tabs.image')} <Badge variant="outline" className="ml-1">{documentTypeCounts.image}</Badge>
          </TabsTrigger>
          <TabsTrigger value="video">
            {t('dataset.document.tabs.video')} <Badge variant="outline" className="ml-1">{documentTypeCounts.video}</Badge>
          </TabsTrigger>
          <TabsTrigger value="website">
            {t('dataset.document.tabs.website')} <Badge variant="outline" className="ml-1">{documentTypeCounts.website}</Badge>
          </TabsTrigger>
          <TabsTrigger value="knowledge">
            {t('dataset.document.tabs.knowledge')} <Badge variant="outline" className="ml-1">{documentTypeCounts.knowledge}</Badge>
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </div>
  )
}
