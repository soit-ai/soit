import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'

export function ConversationSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>对话设置</CardTitle>
        <CardDescription>设置机器人的对话行为和界面展示</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label className="text-base">欢迎消息</Label>
            <p className="text-sm text-muted-foreground">当用户首次与机器人交互时显示的消息</p>
          </div>
          <Switch checked={true} />
        </div>
        <Textarea
          placeholder="输入欢迎消息"
          className="min-h-[80px]"
          defaultValue="您好！我是客服助手，可以回答您关于产品的问题。请问有什么可以帮助您的？"
        />
        
        <Separator />
        
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="max-context">最大上下文长度</Label>
            <Select defaultValue="10">
              <SelectTrigger id="max-context">
                <SelectValue placeholder="选择长度" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5">5 条消息</SelectItem>
                <SelectItem value="10">10 条消息</SelectItem>
                <SelectItem value="20">20 条消息</SelectItem>
                <SelectItem value="50">50 条消息</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="response-time">响应时间控制</Label>
            <Select defaultValue="normal">
              <SelectTrigger id="response-time">
                <SelectValue placeholder="选择速度" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="fast">快速响应</SelectItem>
                <SelectItem value="normal">正常速度</SelectItem>
                <SelectItem value="thoughtful">思考模式</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label className="text-base">显示打字指示器</Label>
            <p className="text-sm text-muted-foreground">当机器人正在生成回复时显示打字动画</p>
          </div>
          <Switch checked={true} />
        </div>
        
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label className="text-base">允许用户评分</Label>
            <p className="text-sm text-muted-foreground">允许用户对机器人回复进行评分和反馈</p>
          </div>
          <Switch checked={true} />
        </div>
      </CardContent>
    </Card>
  )
}
