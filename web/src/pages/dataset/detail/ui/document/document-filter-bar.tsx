import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Search } from 'lucide-react'
import { useTranslation } from '@/i18n'

// Document type enum.
const DocumentType = {
  DOCUMENT: 'document',
  IMAGE: 'image',
  VIDEO: 'video',
  LINK: 'link',
  WEBSITE: 'website',
} as const

interface DocumentFilterBarProps {
  searchQuery: string
  selectedType: string
  onSearchChange: (value: string) => void
  onTypeChange: (value: string) => void
}

export function DocumentFilterBar({
  searchQuery,
  selectedType,
  onSearchChange,
  onTypeChange
}: DocumentFilterBarProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t('dataset.document.filter.searchPlaceholder')}
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-[200px]"
        />
      </div>
      <Select value={selectedType} onValueChange={onTypeChange}>
        <SelectTrigger className="w-[120px]">
          <SelectValue placeholder={t('dataset.document.filter.typePlaceholder')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('dataset.document.filter.types.all')}</SelectItem>
          <SelectItem value={DocumentType.DOCUMENT}>{t('dataset.document.filter.types.document')}</SelectItem>
          <SelectItem value={DocumentType.IMAGE}>{t('dataset.document.filter.types.image')}</SelectItem>
          <SelectItem value={DocumentType.VIDEO}>{t('dataset.document.filter.types.video')}</SelectItem>
          <SelectItem value={DocumentType.LINK}>{t('dataset.document.filter.types.link')}</SelectItem>
          <SelectItem value={DocumentType.WEBSITE}>{t('dataset.document.filter.types.website')}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
