import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Code, Copy, ExternalLink, Globe, Info, Link, MessageCircle, Pause, Play, RefreshCw, Settings, Share2, Terminal, Upload, Zap } from 'lucide-react'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useState } from 'react'
import { Codebox } from '@/components/ui/codebox'

interface WebAppTabProps {
  webAppStatus: string;
  onOpenEmbedDialog: () => void;
}

export function WebAppTab({ webAppStatus, onOpenEmbedDialog }: WebAppTabProps) {
  const [embedType, setEmbedType] = useState('link')
  const [buttonColor, setButtonColor] = useState('#1C64F2')
  const [windowSize, setWindowSize] = useState('medium')
  const [embedWidth, setEmbedWidth] = useState('100%')
  const [embedHeight, setEmbedHeight] = useState('600')
  const [showEmbedCode, setShowEmbedCode] = useState(false)
  
  const handleCopyCode = () => {
    if (embedType === 'link') {
      navigator.clipboard.writeText("https://soit.app/chat/YOUR_EMBED_TOKEN")
    } else if (embedType === 'embed') {
      const iframeCode = `<iframe src="https://soit.app/chat/YOUR_EMBED_TOKEN" width="${embedWidth}" height="${embedHeight}" frameborder="0"></iframe>`
      navigator.clipboard.writeText(iframeCode)
    } else if (embedType === 'float') {
      let width = '24rem'
      let height = '40rem'
      if (windowSize === 'small') {
        width = '20rem'
        height = '30rem'
      } else if (windowSize === 'large') {
        width = '28rem'
        height = '45rem'
      }
      
      const jsCode = `<script>
  window.soitChatbotConfig = {
    token: 'YOUR_EMBED_TOKEN',
    systemVariables: {
      // user_id: 'YOU CAN DEFINE USER ID HERE',
      // conversation_id: 'YOU CAN DEFINE CONVERSATION ID HERE, IT MUST BE A UUID'
    },
  }
</script>
<script
  src="https://soit.app/embed.min.js"
  id="YOUR_EMBED_TOKEN"
  defer>
</script>
<style>
  #soit-chatbot-bubble-button {
    background-color: ${buttonColor} !important;
  }
  #soit-chatbot-bubble-window {
    width: ${width} !important;
    height: ${height} !important;
  }
</style>`
      navigator.clipboard.writeText(jsCode)
    }
  }
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>开箱即用的 Web APP</CardTitle>
            <CardDescription>可直接分享给用户的聊天界面</CardDescription>
          </div>
          <Badge className={`${webAppStatus === '运行中' ? 'bg-green-500' : 'bg-yellow-500'}`}>
            {webAppStatus}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="rounded-lg border p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-4">
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <Globe className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="text-base font-semibold">公开访问 URL</h3>
                  <p className="text-sm text-muted-foreground">用户可以通过此链接直接访问聊天界面</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" onClick={onOpenEmbedDialog}>
                  <Share2 className="h-4 w-4 mr-1" />
                  嵌入到网站
                </Button>
                <Button variant="outline" size="sm">
                  <Settings className="h-4 w-4 mr-1" />
                  设置
                </Button>
              </div>
            </div>
            
            <div className="flex items-center space-x-2 bg-muted p-2 rounded-md">
              <Input 
                readOnly 
                value="https://soit.app/chat/YOUR_EMBED_TOKEN" 
                className="flex-1 bg-transparent border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              />
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <Copy className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>复制链接</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>在新窗口打开</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border p-4">
              <div className="flex items-center space-x-3 mb-3">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Zap className="h-4 w-4 text-primary" />
                </div>
                <h3 className="text-sm font-medium">快速操作</h3>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" size="sm" className="justify-start">
                  <Play className="h-4 w-4 mr-2" />
                  启动
                </Button>
                <Button variant="outline" size="sm" className="justify-start">
                  <Pause className="h-4 w-4 mr-2" />
                  暂停
                </Button>
                <Button variant="outline" size="sm" className="justify-start">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  重启
                </Button>
                <Button variant="outline" size="sm" className="justify-start">
                  <Terminal className="h-4 w-4 mr-2" />
                  日志
                </Button>
              </div>
            </div>
            
            <div className="rounded-lg border p-4">
              <div className="flex items-center space-x-3 mb-3">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Settings className="h-4 w-4 text-primary" />
                </div>
                <h3 className="text-sm font-medium">配置选项</h3>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="custom-domain" className="text-sm">自定义域名</Label>
                  <Switch id="custom-domain" />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="password-protection" className="text-sm">密码保护</Label>
                  <Switch id="password-protection" />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="auto-update" className="text-sm">自动更新</Label>
                  <Switch id="auto-update" defaultChecked />
                </div>
              </div>
            </div>
          </div>
          
          <div className="rounded-lg border p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-3">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Code className="h-4 w-4 text-primary" />
                </div>
                <h3 className="text-sm font-medium">嵌入选项</h3>
              </div>
              <Button variant="outline" size="sm" onClick={() => setShowEmbedCode(!showEmbedCode)}>
                {showEmbedCode ? '隐藏嵌入代码' : '查看嵌入代码'}
              </Button>
            </div>
            <p className="text-sm text-muted-foreground mb-3">将聊天界面嵌入到您自己的网站中，点击上方按钮查看详细嵌入代码</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className={`border rounded-md p-3 flex flex-col items-center justify-center text-center cursor-pointer ${!showEmbedCode && embedType === 'link' ? 'ring-2 ring-primary' : ''}`} onClick={() => { setEmbedType('link'); setShowEmbedCode(true); }}>
                <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center mb-2">
                  <Link className="h-5 w-5 text-blue-600" />
                </div>
                <h4 className="text-sm font-medium mb-1">链接方式</h4>
                <p className="text-xs text-muted-foreground">分享链接给用户直接访问</p>
              </div>
              <div className={`border rounded-md p-3 flex flex-col items-center justify-center text-center cursor-pointer ${!showEmbedCode && embedType === 'embed' ? 'ring-2 ring-primary' : ''}`} onClick={() => { setEmbedType('embed'); setShowEmbedCode(true); }}>
                <div className="h-10 w-10 rounded-full bg-purple-100 flex items-center justify-center mb-2">
                  <Code className="h-5 w-5 text-purple-600" />
                </div>
                <h4 className="text-sm font-medium mb-1">嵌入方式</h4>
                <p className="text-xs text-muted-foreground">使用iframe嵌入到网页中</p>
              </div>
              <div className={`border rounded-md p-3 flex flex-col items-center justify-center text-center cursor-pointer ${!showEmbedCode && embedType === 'float' ? 'ring-2 ring-primary' : ''}`} onClick={() => { setEmbedType('float'); setShowEmbedCode(true); }}>
                <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center mb-2">
                  <MessageCircle className="h-5 w-5 text-green-600" />
                </div>
                <h4 className="text-sm font-medium mb-1">悬浮按钮</h4>
                <p className="text-xs text-muted-foreground">添加悬浮聊天按钮</p>
              </div>
            </div>
            
            {showEmbedCode && (
              <div className="mt-6 border-t pt-4">
                <Tabs value={embedType} onValueChange={setEmbedType} className="w-full">
                  <TabsList className="flex w-full">
                    <TabsTrigger value="link" className="flex-1">链接方式</TabsTrigger>
                    <TabsTrigger value="embed" className="flex-1">嵌入方式</TabsTrigger>
                    <TabsTrigger value="float" className="flex-1">悬浮按钮</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="link" className="mt-4 space-y-4">
                    <div className="space-y-4">
                      <div className="flex items-center space-x-2 bg-muted p-3 rounded-md">
                        <Input 
                          readOnly 
                          value="https://soit.app/chat/YOUR_EMBED_TOKEN" 
                          className="flex-1 bg-transparent border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
                        />
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => {
                          navigator.clipboard.writeText("https://soit.app/chat/YOUR_EMBED_TOKEN");
                        }}>
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="flex justify-end">
                        <Button variant="outline" size="sm" onClick={() => window.open("https://soit.app/chat/YOUR_EMBED_TOKEN", "_blank")}>
                          在新窗口打开
                        </Button>
                      </div>
                    </div>
                  </TabsContent>
                  
                  <TabsContent value="embed" className="mt-4 space-y-4">
                    <div className="space-y-4">
                      <div>
                        <Label className="text-sm mb-2 block">iframe 代码</Label>
                        <Codebox
                          language="html"
                          code={`<iframe src="https://soit.app/chat/YOUR_EMBED_TOKEN" width="${embedWidth}" height="${embedHeight}" frameborder="0"></iframe>`}
                          className="mb-2"
                          showLineNumbers={true}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor="embed-width" className="text-sm mb-2 block">宽度</Label>
                          <Input 
                            id="embed-width" 
                            value={embedWidth}
                            onChange={(e) => setEmbedWidth(e.target.value)}
                          />
                        </div>
                        <div>
                          <Label htmlFor="embed-height" className="text-sm mb-2 block">高度</Label>
                          <Input 
                            id="embed-height" 
                            value={embedHeight}
                            onChange={(e) => setEmbedHeight(e.target.value)}
                          />
                        </div>
                      </div>
                      <div className="mt-4">
                        <Button variant="outline" size="sm" className="w-full" onClick={() => {
                          const iframeCode = `<iframe src="https://soit.app/chat/YOUR_EMBED_TOKEN" width="${embedWidth}" height="${embedHeight}" frameborder="0"></iframe>`;
                          navigator.clipboard.writeText(iframeCode);
                        }}>
                          <Copy className="h-4 w-4 mr-2" />
                          复制自定义代码
                        </Button>
                      </div>
                    </div>
                  </TabsContent>
                  
                  <TabsContent value="float" className="mt-4 space-y-4">
                    <div className="space-y-4">
                      <div>
                        <Label className="text-sm mb-2 block">JavaScript 代码</Label>
                        <Codebox
                          language="html"
                          code={`<script>
  window.soitChatbotConfig = {
    token: 'YOUR_EMBED_TOKEN',
    systemVariables: {
      // user_id: 'YOU CAN DEFINE USER ID HERE',
      // conversation_id: 'YOU CAN DEFINE CONVERSATION ID HERE, IT MUST BE A UUID'
    },
  }
</script>
<script
  src="https://soit.app/embed.min.js"
  id="YOUR_EMBED_TOKEN"
  defer>
</script>
<style>
  #soit-chatbot-bubble-button {
    background-color: ${buttonColor} !important;
  }
  #soit-chatbot-bubble-window {
    width: ${windowSize === 'small' ? '20rem' : windowSize === 'large' ? '28rem' : '24rem'} !important;
    height: ${windowSize === 'small' ? '30rem' : windowSize === 'large' ? '45rem' : '40rem'} !important;
  }
</style>`}
                          className="mb-2"
                          showLineNumbers={true}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor="button-color" className="text-sm mb-2 block">按钮颜色</Label>
                          <div className="flex items-center space-x-2">
                            <Input 
                              id="button-color" 
                              value={buttonColor}
                              onChange={(e) => setButtonColor(e.target.value)}
                            />
                            <div className="h-8 w-8 rounded-md" style={{ backgroundColor: buttonColor }}></div>
                          </div>
                        </div>
                        <div>
                          <Label htmlFor="window-size" className="text-sm mb-2 block">窗口尺寸</Label>
                          <Select value={windowSize} onValueChange={setWindowSize}>
                            <SelectTrigger>
                              <SelectValue placeholder="选择尺寸" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="small">小 (320x480)</SelectItem>
                              <SelectItem value="medium">中 (384x640)</SelectItem>
                              <SelectItem value="large">大 (448x720)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="mt-4">
                        <Button variant="outline" size="sm" className="w-full" onClick={handleCopyCode}>
                          <Copy className="h-4 w-4 mr-2" />
                          复制自定义代码
                        </Button>
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            )}
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center">
            <Info className="h-4 w-4 text-muted-foreground mr-1" />
            <span className="text-sm text-muted-foreground">上次部署: 2023-08-15 14:30</span>
          </div>
          <Button>
            <Upload className="h-4 w-4 mr-1" />
            重新部署
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
