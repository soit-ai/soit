import { useTranslation } from '@/i18n'
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { toast } from '@/hooks/use-toast'
import { Bell, Mail, MessageSquare, Calendar, Clock, Smartphone, Globe, Settings, AlertCircle, CheckCircle2 } from 'lucide-react'
function Page() {
  const { t } = useTranslation()
  
  // 通知设置状态
  const [systemNotifications, setSystemNotifications] = useState(true)
  const [securityAlerts, setSecurityAlerts] = useState(true)
  const [accountUpdates, setAccountUpdates] = useState(true)
  const [newFeatures, setNewFeatures] = useState(true)
  const [marketingNotifications, setMarketingNotifications] = useState(false)
  
  // 聊天通知设置
  const [chatMessages, setChatMessages] = useState(true)
  const [chatMentions, setChatMentions] = useState(true)
  const [chatReactions, setChatReactions] = useState(true)
  
  // 任务通知设置
  const [taskAssignments, setTaskAssignments] = useState(true)
  const [taskDeadlines, setTaskDeadlines] = useState(true)
  const [taskUpdates, setTaskUpdates] = useState(true)
  
  // 通知偏好设置
  const [notificationMethod, setNotificationMethod] = useState("all")
  const [emailFrequency, setEmailFrequency] = useState("instant")
  const [quietHours, setQuietHours] = useState(false)
  const [quietHoursStart, setQuietHoursStart] = useState("22:00")
  const [quietHoursEnd, setQuietHoursEnd] = useState("07:00")
  
  // 保存通知设置
  const handleSaveNotificationSettings = () => {
    // 这里应该有API调用来保存设置
    toast({
      title: '设置已保存',
      description: '您的通知偏好已更新',
    })
  }
  
  // 测试通知
  const handleTestNotification = () => {
    // 这里应该有API调用来发送测试通知
    toast({
      title: '测试通知已发送',
      description: '请检查您的设备以确认通知设置正常工作',
    })
  }
  
  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">通知设置</h3>
          <p className="text-sm text-muted-foreground mt-1">管理您接收的通知类型和方式</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleTestNotification}>
            <Bell className="mr-2 h-4 w-4" />
            测试通知
          </Button>
          <Button onClick={handleSaveNotificationSettings}>保存设置</Button>
        </div>
      </div>

      <Tabs defaultValue="system" className="w-full">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="system">系统通知</TabsTrigger>
          <TabsTrigger value="chat">聊天通知</TabsTrigger>
          <TabsTrigger value="task">任务通知</TabsTrigger>
          <TabsTrigger value="preferences">通知偏好</TabsTrigger>
        </TabsList>
        
        {/* 系统通知标签页 */}
        <TabsContent value="system">
          <Card>
            <CardHeader>
              <CardTitle>系统通知</CardTitle>
              <CardDescription>控制您接收的系统相关通知</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">系统状态</Label>
                  <p className="text-sm text-muted-foreground">
                    有关系统维护、更新和状态变化的通知
                  </p>
                </div>
                <Switch
                  checked={systemNotifications}
                  onCheckedChange={setSystemNotifications}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">安全提醒</Label>
                  <p className="text-sm text-muted-foreground">
                    有关账户安全、可疑登录和重要安全更新的通知
                  </p>
                </div>
                <Switch
                  checked={securityAlerts}
                  onCheckedChange={setSecurityAlerts}
                  disabled={true} // 安全提醒不可禁用
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">账户更新</Label>
                  <p className="text-sm text-muted-foreground">
                    有关您账户状态、订阅和付款的通知
                  </p>
                </div>
                <Switch
                  checked={accountUpdates}
                  onCheckedChange={setAccountUpdates}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">新功能公告</Label>
                  <p className="text-sm text-muted-foreground">
                    有关新功能、改进和产品更新的通知
                  </p>
                </div>
                <Switch
                  checked={newFeatures}
                  onCheckedChange={setNewFeatures}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">营销通知</Label>
                  <p className="text-sm text-muted-foreground">
                    有关促销、优惠和活动的通知
                  </p>
                </div>
                <Switch
                  checked={marketingNotifications}
                  onCheckedChange={setMarketingNotifications}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 聊天通知标签页 */}
        <TabsContent value="chat">
          <Card>
            <CardHeader>
              <CardTitle>聊天通知</CardTitle>
              <CardDescription>控制您接收的聊天相关通知</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">新消息</Label>
                  <p className="text-sm text-muted-foreground">
                    当您收到新消息时通知您
                  </p>
                </div>
                <Switch
                  checked={chatMessages}
                  onCheckedChange={setChatMessages}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">提及和回复</Label>
                  <p className="text-sm text-muted-foreground">
                    当有人提及或回复您时通知您
                  </p>
                </div>
                <Switch
                  checked={chatMentions}
                  onCheckedChange={setChatMentions}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">表情反应</Label>
                  <p className="text-sm text-muted-foreground">
                    当有人对您的消息添加表情反应时通知您
                  </p>
                </div>
                <Switch
                  checked={chatReactions}
                  onCheckedChange={setChatReactions}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 任务通知标签页 */}
        <TabsContent value="task">
          <Card>
            <CardHeader>
              <CardTitle>任务通知</CardTitle>
              <CardDescription>控制您接收的任务相关通知</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">任务分配</Label>
                  <p className="text-sm text-muted-foreground">
                    当任务分配给您时通知您
                  </p>
                </div>
                <Switch
                  checked={taskAssignments}
                  onCheckedChange={setTaskAssignments}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">截止日期提醒</Label>
                  <p className="text-sm text-muted-foreground">
                    在任务截止日期前提醒您
                  </p>
                </div>
                <Switch
                  checked={taskDeadlines}
                  onCheckedChange={setTaskDeadlines}
                />
              </div>
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">任务更新</Label>
                  <p className="text-sm text-muted-foreground">
                    当您的任务有更新或评论时通知您
                  </p>
                </div>
                <Switch
                  checked={taskUpdates}
                  onCheckedChange={setTaskUpdates}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* 通知偏好标签页 */}
        <TabsContent value="preferences">
          <Card>
            <CardHeader>
              <CardTitle>通知偏好</CardTitle>
              <CardDescription>设置您接收通知的方式和时间</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label className="text-base">通知方式</Label>
                <RadioGroup value={notificationMethod} onValueChange={setNotificationMethod} className="mt-2">
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="all" id="all" />
                    <Label htmlFor="all" className="cursor-pointer">
                      所有渠道（应用内、邮件和推送）
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="app" id="app" />
                    <Label htmlFor="app" className="cursor-pointer">
                      仅应用内通知
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="email" id="email" />
                    <Label htmlFor="email" className="cursor-pointer">
                      仅电子邮件
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="push" id="push" />
                    <Label htmlFor="push" className="cursor-pointer">
                      仅推送通知
                    </Label>
                  </div>
                </RadioGroup>
              </div>
              
              <div className="space-y-2">
                <Label className="text-base">电子邮件摘要频率</Label>
                <Select value={emailFrequency} onValueChange={setEmailFrequency}>
                  <SelectTrigger className="w-full md:w-[250px]">
                    <SelectValue placeholder="选择频率" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instant">即时发送</SelectItem>
                    <SelectItem value="daily">每日摘要</SelectItem>
                    <SelectItem value="weekly">每周摘要</SelectItem>
                    <SelectItem value="none">不发送邮件</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-base">免打扰时间</Label>
                  <Switch
                    checked={quietHours}
                    onCheckedChange={setQuietHours}
                  />
                </div>
                
                {quietHours && (
                  <div className="flex items-center gap-4 mt-2">
                    <div className="space-y-1">
                      <Label>开始时间</Label>
                      <Select value={quietHoursStart} onValueChange={setQuietHoursStart}>
                        <SelectTrigger className="w-[120px]">
                          <SelectValue placeholder="开始时间" />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 24 }).map((_, i) => (
                            <SelectItem key={i} value={`${i.toString().padStart(2, '0')}:00`}>
                              {`${i.toString().padStart(2, '0')}:00`}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-1">
                      <Label>结束时间</Label>
                      <Select value={quietHoursEnd} onValueChange={setQuietHoursEnd}>
                        <SelectTrigger className="w-[120px]">
                          <SelectValue placeholder="结束时间" />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 24 }).map((_, i) => (
                            <SelectItem key={i} value={`${i.toString().padStart(2, '0')}:00`}>
                              {`${i.toString().padStart(2, '0')}:00`}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
                
                {quietHours && (
                  <p className="text-sm text-muted-foreground mt-2">
                    在免打扰时间内，您将不会收到任何通知，但它们会在免打扰时间结束后显示。
                  </p>
                )}
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline">
                <Settings className="mr-2 h-4 w-4" />
                重置为默认设置
              </Button>
              <Button onClick={handleSaveNotificationSettings}>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                保存偏好
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Page
