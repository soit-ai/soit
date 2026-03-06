import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Upload } from 'lucide-react'

interface AvatarSettingsProps {
  botInfo: {
    name: string;
    avatar: string;
  }
}

export function AvatarSettings({ botInfo }: AvatarSettingsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>头像和图标设置</CardTitle>
        <CardDescription>自定义机器人的头像和图标风格</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>头像风格</Label>
          <div className="grid grid-cols-5 gap-4">
            {[
              { style: 'photo', name: '真实照片', avatar: '/avatars/bot-photo.png' },
              { style: 'cartoon', name: '卡通风格', avatar: '/avatars/bot-cartoon.png' },
              { style: 'robot', name: '机器人', avatar: '/avatars/bot-robot.png' },
              { style: 'abstract', name: '抽象图形', avatar: '/avatars/bot-abstract.png' },
              { style: 'custom', name: '自定义', avatar: '/avatars/bot-custom.png' }
            ].map((style, index) => (
              <div key={index} className="flex flex-col items-center gap-2">
                <Avatar className={`h-16 w-16 ${index === 0 ? 'ring-2 ring-primary ring-offset-2' : ''}`}>
                  <AvatarImage src={style.avatar} />
                  <AvatarFallback>BOT</AvatarFallback>
                </Avatar>
                <p className="text-xs font-medium">{style.name}</p>
              </div>
            ))}
          </div>
        </div>
        
        <div className="space-y-2 pt-4">
          <Label>自定义头像</Label>
          <div className="flex items-center gap-4">
            <Avatar className="h-20 w-20">
              <AvatarImage src={botInfo.avatar} />
              <AvatarFallback>{botInfo.name.slice(0, 2)}</AvatarFallback>
            </Avatar>
            <div className="space-y-2">
              <Button variant="outline">
                <Upload className="mr-2 h-4 w-4" />
                上传新头像
              </Button>
              <p className="text-xs text-muted-foreground">推荐使用正方形图片，尺寸至少为 256x256 像素</p>
            </div>
          </div>
        </div>
        
        <Separator />
        
        <div className="space-y-2">
          <Label>图标风格</Label>
          <div className="grid grid-cols-3 gap-4">
            <div className="overflow-hidden rounded-lg border p-2">
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-16 items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                </div>
                <p className="text-sm font-medium">线条图标</p>
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">当前选择</Badge>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border p-2">
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-16 items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1s1 .45 1 1v4c0 .55-.45 1-1 1zm1-8h-2V6h2v2z"/></svg>
                </div>
                <p className="text-sm font-medium">填充图标</p>
                <Button size="sm" variant="outline" className="h-7 w-full text-xs">选择</Button>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border p-2">
              <div className="flex flex-col items-center gap-2">
                <div className="flex h-16 items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" fill="#e6f7ff"/><path d="M12 16v-4" stroke="#0ea5e9"/><path d="M12 8h.01" stroke="#0ea5e9"/></svg>
                </div>
                <p className="text-sm font-medium">双色图标</p>
                <Button size="sm" variant="outline" className="h-7 w-full text-xs">选择</Button>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
