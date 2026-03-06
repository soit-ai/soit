import React from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Carousel, CarouselContent, CarouselItem, CarouselNext, CarouselPrevious } from '@/components/ui/carousel'
import { Badge } from '@/components/ui/badge'
import { ArrowRight } from 'lucide-react'

export interface FeaturedItemProps {
  id: string
  title: string
  description: string
  imageUrl: string
  badgeText?: string
  buttonText?: string
  onClick?: (id: string) => void
}

export interface StoreFeaturedProps {
  items: FeaturedItemProps[]
  onInstall?: (id: string) => void
  onView?: (id: string) => void
}

export function StoreFeatured({ items, onInstall, onView }: StoreFeaturedProps) {
  const { t } = useTranslation()

  if (!items.length) return null
  
  const handleClick = (id: string) => {
    if (onView) onView(id)
  }

  return (
    <div className="store-featured mb-8">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-bold">精选</h3>
        <Button variant="link" size="sm" className="gap-1">
          查看全部 <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      <Carousel className="w-full">
        <CarouselContent>
          {items.map((item) => (
            <CarouselItem key={item.id} className="md:basis-1/2 lg:basis-1/3">
              <Card className="overflow-hidden border-0 shadow-lg">
                <div className="relative">
                  <img 
                    src={item.imageUrl} 
                    alt={item.title} 
                    className="h-[200px] w-full object-cover"
                  />
                  {item.badgeText && (
                    <Badge className="absolute right-3 top-3 bg-primary">
                      {item.badgeText}
                    </Badge>
                  )}
                </div>
                <CardContent className="p-6">
                  <div className="p-4">
                    <h3 className="mb-2 text-xl font-semibold">{item.title}</h3>
                    <p className="mb-4 text-sm text-muted-foreground">{item.description}</p>
                    <Button 
                      onClick={() => item.onClick ? item.onClick(item.id) : onView?.(item.id)} 
                      className="w-full"
                    >
                      {item.buttonText || '了解更多'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </CarouselItem>
          ))}
        </CarouselContent>
        <CarouselPrevious className="left-2" />
        <CarouselNext className="right-2" />
      </Carousel>
    </div>
  )
}
