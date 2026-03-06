import React from 'react'
import { useTranslation } from '@/i18n'
import { Button } from '@/components/ui/button'
import { StoreItemCard } from './store-item-card'
import type { StoreItemProps } from './store-item-card'
import { ArrowRight } from 'lucide-react'

interface StoreCategorySectionProps {
  title: string
  items: StoreItemProps[]
  viewAllLink?: string
  onViewAll?: () => void
  onInstall?: (id: string) => void
  onView?: (id: string) => void
}

export function StoreCategorySection({ 
  title, 
  items, 
  viewAllLink, 
  onViewAll, 
  onInstall, 
  onView 
}: StoreCategorySectionProps) {
  const { t } = useTranslation()

  if (!items.length) return null

  return (
    <div className="store-category-section mb-10">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-bold">{title}</h3>
        <Button 
          variant="link" 
          size="sm" 
          className="gap-1"
          onClick={onViewAll}
        >
          查看全部 <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {items.slice(0, 8).map((item) => (
          <StoreItemCard 
            key={item.id} 
            {...item} 
            onInstall={onInstall}
            onView={onView}
          />
        ))}
      </div>
    </div>
  )
}
