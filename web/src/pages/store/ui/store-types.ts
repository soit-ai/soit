import type { StoreItemProps } from './store-item-card'
import type { FeaturedItemProps } from './store-featured'

export type StoreCategory = 'all' | 'plugin' | 'agent' | 'service' | 'template' | 'model' | 'application'

export interface StoreFilterOptions {
  category: StoreCategory
  query: string
  sort: 'popular' | 'newest' | 'rating'
}

export type StoreState = {
  items: StoreItemProps[]
  featuredItems: FeaturedItemProps[]
  filteredItems: StoreItemProps[]
  selectedItem: StoreItemProps | null
  isDetailOpen: boolean
  isLoading: boolean
  filterOptions: StoreFilterOptions
}
