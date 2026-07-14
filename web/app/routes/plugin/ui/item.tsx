import { Button } from '@/components/ui/button'
import { SquarePlay } from 'lucide-react'
import { BoxCard } from '@/components/ui/app/box-card'

export function Item(props: { item?: any; index: number }) {
  const { item = {}, index } = props

  const onClick = () => {
  }
  const renderButton = () => (
    <Button size="icon" type="button" variant="default" className="h-6" onClick={onClick}>
      <SquarePlay />
    </Button>
  )
  const mainBtn = item.mainBtn || renderButton()
  return (
    <BoxCard
      key={index}
      title={item.title}
      subtitle={item.subtitle}
      icon={item.icon}
      iconType={item.iconType}
      tags={item.tags}
      mainBtn={mainBtn}
      mark={item.mark}
    >
      {item.desc}
    </BoxCard>
  )
}

export default Item
