import { useState, type ReactElement } from 'react'
import { AppIcon } from '@/components/ui/app/app-icon'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

// type props
export interface BoxCardProps {
  title?: string | ReactElement // title of the card
  subtitle?: string | ReactElement // subtitle of the card
  tags?: string[] // tags of the card
  icon?: any
  iconType?: 'icon' | 'emoji' | 'image'
  children?: any
  header?: ReactElement
  footer?: ReactElement
  onClick?: () => void
  mainBtn?: ReactElement
  badge?: ReactElement | null
  mark?: string | null
}

export function BoxHeader(props: { title: string; subtitle?: string; icon?: any; iconType?: 'icon' | 'emoji' | 'image'; iconHover?: ReactElement; right?: ReactElement; onClick?: () => void }) {
  const { title, subtitle, icon, iconType, iconHover, right } = props
  return (
    <div className="flex flex-row justify-between items-center overflow-hidden" onClick={props.onClick}>
      <div className="flex flex-row h-full items-center overflow-hidden">
        <AppIcon icon={icon} type={iconType} iconHover={iconHover} />
        <div className="pl-2 space-y-1 overflow-hidden">
          {typeof title == 'string' || title == null || title == undefined ? <CardTitle className="text-sm" dangerouslySetInnerHTML={{ __html: title || '&nbsp;' }}></CardTitle> : title}
          {typeof subtitle == 'string' || subtitle == null || subtitle == undefined ? (
            <CardDescription className="text-xs truncate overflow-hidden" dangerouslySetInnerHTML={{ __html: subtitle || '&nbsp;' }}></CardDescription>
          ) : (
            subtitle
          )}
        </div>
        {right ? <div className="self-center justify-center w-[20px]">{right}</div> : null}
      </div>
    </div>
  )
}

export function BoxCard(props: BoxCardProps) {
  const { title, subtitle, icon, iconType = 'icon', children, header, footer, mainBtn, tags = [], badge = null, mark = null } = props
  return (
    <Card className="py-1 gap-0">
      <CardHeader className="p-3 relative">
        {header ? (
          header
        ) : (
          <div className="flex flex-row justify-between items-center overflow-hidden" onClick={props.onClick}>
            <div className="flex flex-row h-full items-center overflow-hidden">
              <AppIcon icon={icon} type={iconType} />
              <div className="pl-2 space-y-1 overflow-hidden">
                {typeof title == 'string' || title == null || title == undefined ? <CardTitle className="text-sm" dangerouslySetInnerHTML={{ __html: title || '&nbsp;' }}></CardTitle> : title}
                {typeof subtitle == 'string' || subtitle == null || subtitle == undefined ? (
                  <CardDescription className="text-xs truncate overflow-hidden" dangerouslySetInnerHTML={{ __html: subtitle || '&nbsp;' }}></CardDescription>
                ) : (
                  subtitle
                )}
              </div>
            </div>
            {/* <div className="pl-2 space-y-1 self-start justify-end">
            <Button size={'icon'} type="button" variant="secondary" className="h-6">
              <Settings2></Settings2>
            </Button>
          </div> */}
          </div>
        )}
        <div className="absolute top-[-10px] right-[-5px]">{badge}</div>
        {mark ? (
          <Badge variant="secondary" className="absolute top-3 right-0 text-[10px] font-normal text-center">
            {mark}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="p-3 pt-0 pb-0">
        {typeof children !== 'string' && (children != null || children != undefined) ? (
          children
        ) : (
          <div className="flex flex-row h-[66px] justify-start items-start overflow-hidden">
            <p className="text-xs text-muted-foreground text-wrap truncate" dangerouslySetInnerHTML={{ __html: children }}></p>
          </div>
        )}
      </CardContent>
      <CardFooter className="p-3 pt-1">
        {footer ? (
          footer
        ) : (
          <div className="flex flex-row flex-1 justify-between pt-1">
            <div className="flex flex-row flex-1 gap-1 justify-start items-center flex-wrap">
              {tags?.map((_tag: string, index: number) => (
                <Badge key={index} variant="secondary" className="h-4 pl-1 pr-1 text-[10px] font-normal text-center ">
                  {_tag}
                </Badge>
              ))}
            </div>
            <div className="flex flex-row gap-2 h-6">{mainBtn ? mainBtn : ``}</div>
          </div>
        )}
      </CardFooter>
    </Card>
  )
}

export default BoxCard
