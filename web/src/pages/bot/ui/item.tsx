import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { FlameIcon, MessagesSquare, Send } from 'lucide-react'
import { type BoxCardProps, BoxCard } from '@/components/ui/app/box-card'
import { useNavigate } from '@/hooks/use-navigate'

export function Item(props: { item?: any; index: number }) {
  const { item = {}, index } = props
  const navigate = useNavigate()

  const onClick = () => {
    navigate(`/bot/${item.id}/build`)
  }
  const renderButton = () => {
    return (
      <Button size={'icon'} type="button" variant="default" className="h-6" onClick={onClick}>
        <MessagesSquare />
      </Button>
    )
  }
  return (
    <BoxCard
      key={index}
      title={item.title}
      subtitle={item.subtitle}
      icon={item.icon}
      iconType={item.iconType}
      tags={item.tags}
      mainBtn={renderButton()}
      badge={item?.hot ? <FlameIcon color="red" size={22} /> : null}
      mark={item.mark}
    >
      {item.desc}
    </BoxCard>
  )
}

export default Item
