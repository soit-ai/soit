import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

interface ChatInterfaceSettingsProps {
  botInfo: {
    name: string;
    avatar: string;
  }
}

export function ChatInterfaceSettings({ botInfo }: ChatInterfaceSettingsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>聊天界面设置</CardTitle>
        <CardDescription>自定义聊天界面的布局和样式</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="message-style">消息气泡样式</Label>
            <Select defaultValue="rounded">
              <SelectTrigger id="message-style">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="rounded">圆角气泡</SelectItem>
                <SelectItem value="square">方形气泡</SelectItem>
                <SelectItem value="minimal">极简风格</SelectItem>
                <SelectItem value="chat">聊天风格</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="layout-style">布局方式</Label>
            <Select defaultValue="default">
              <SelectTrigger id="layout-style">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">默认布局</SelectItem>
                <SelectItem value="centered">居中布局</SelectItem>
                <SelectItem value="compact">紧凑布局</SelectItem>
                <SelectItem value="wide">宽幅布局</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="space-y-2">
          <Label>消息气泡预览</Label>
          <div className="rounded-lg border p-4">
            <div className="mb-4 flex items-start gap-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src="/avatars/user-1.png" />
                <AvatarFallback>U</AvatarFallback>
              </Avatar>
              <div className="rounded-lg rounded-tl-none bg-muted p-3">
                <p className="text-sm">你好，我想了解一下你们的产品功能。</p>
              </div>
            </div>
            
            <div className="mb-4 flex items-start justify-end gap-3">
              <div className="rounded-lg rounded-tr-none bg-primary p-3 text-primary-foreground">
                <p className="text-sm">您好！非常感谢您的关注。我们的产品提供了智能客服、数据分析和自动化工作流等功能。您想了解哪方面的具体功能？</p>
              </div>
              <Avatar className="h-8 w-8">
                <AvatarImage src={botInfo.avatar} />
                <AvatarFallback>{botInfo.name.slice(0, 1)}</AvatarFallback>
              </Avatar>
            </div>
          </div>
        </div>
        
        <Separator />
        
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">显示时间戳</Label>
              <p className="text-sm text-muted-foreground">在消息旁显示发送时间</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">显示头像</Label>
              <p className="text-sm text-muted-foreground">在消息旁显示用户和机器人头像</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">消息分组</Label>
              <p className="text-sm text-muted-foreground">按时间或主题将消息分组显示</p>
            </div>
            <Switch checked={false} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
