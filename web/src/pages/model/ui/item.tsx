import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { FlameIcon, MessagesSquare, Send, Settings2 } from 'lucide-react'
import { type BoxCardProps, BoxCard } from '@/components/ui/app/box-card'
import { ProviderAppIcon, ProviderTextIcon, ProviderIcon } from './icon'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { SettingSheet } from '../setting/index'
import { useDrawer } from '@/hooks/use-drawer'

export function Item(props: { item?: any; index: number }) {
  const { item = {}, index } = props

  const onClick = () => {
    console.log('clicked')
  }

  const renderHeader = () => {
    return (
      <div className="flex flex-row justify-between items-center">
        <div className="flex flex-row h-full  items-center overflow-hidden ">
          {/* <ProviderIcon name={item.icon} className="h-[44px] w-auto p-1" /> */}
          <ProviderAppIcon name={item.icon} />
          <ProviderTextIcon name={item.iconText} className="h-[36px] w-auto p-2" />
        </div>
      </div>
    )
  }

  const renderButton = () => {
    // Use the useDrawer hook.
    const drawer = useDrawer();
    
    const handleOpenDrawer = () => {
      drawer.open(
        <SettingSheet item={item} index={index} />,
        {
          direction: 'right',
          contentClassName: '!w-[500px] !max-w-[500px] h-full',
        }
      );
    }
    
    return (
      <Button 
        size={'icon'} 
        type="button" 
        variant="default" 
        className="h-6" 
        onClick={handleOpenDrawer}
      >
        <Settings2 />
      </Button>
    )
  }

  return (
    <BoxCard key={index} title={item.name} tags={item.tags} header={renderHeader()} mainBtn={renderButton()}
    badge={item?.hot ? <FlameIcon color="red" size={22} /> : null}
    >
      {item.desc}
    </BoxCard>
  )
}

export default Item
