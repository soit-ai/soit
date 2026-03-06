import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Code, Copy, Link, MessageCircle } from 'lucide-react'
import { useState } from 'react'
import { Codebox } from '@/components/ui/codebox'

export function EmbedCodeTab() {
  const [embedType, setEmbedType] = useState('link')
  const [buttonColor, setButtonColor] = useState('#1C64F2')
  const [windowSize, setWindowSize] = useState('medium')
  const [embedWidth, setEmbedWidth] = useState('100%')
  const [embedHeight, setEmbedHeight] = useState('600')

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
        <CardTitle>嵌入代码</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="py-4">
          <div className="flex items-center justify-center space-x-8 mb-6">
            <div className="flex-1 max-w-[600px]">
              <RadioGroup value={embedType} onValueChange={setEmbedType} className="grid grid-cols-3 gap-4">
                <div className={`border rounded-md p-4 flex flex-col items-center text-center cursor-pointer ${embedType === 'link' ? 'ring-2 ring-primary' : ''}`}>
                  <RadioGroupItem value="link" id="link" className="sr-only" />
                  <Label htmlFor="link" className="cursor-pointer">
                    <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center mb-2">
                      <Link className="h-6 w-6 text-blue-600" />
                    </div>
                    <h4 className="text-sm font-medium mb-1">链接方式</h4>
                    <p className="text-xs text-muted-foreground">分享链接给用户直接访问</p>
                  </Label>
                </div>
                <div className={`border rounded-md p-4 flex flex-col items-center text-center cursor-pointer ${embedType === 'embed' ? 'ring-2 ring-primary' : ''}`}>
                  <RadioGroupItem value="embed" id="embed" className="sr-only" />
                  <Label htmlFor="embed" className="cursor-pointer">
                    <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center mb-2">
                      <Code className="h-6 w-6 text-purple-600" />
                    </div>
                    <h4 className="text-sm font-medium mb-1">嵌入方式</h4>
                    <p className="text-xs text-muted-foreground">使用iframe嵌入到网页中</p>
                  </Label>
                </div>
                <div className={`border rounded-md p-4 flex flex-col items-center text-center cursor-pointer ${embedType === 'float' ? 'ring-2 ring-primary' : ''}`}>
                  <RadioGroupItem value="float" id="float" className="sr-only" />
                  <Label htmlFor="float" className="cursor-pointer">
                    <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mb-2">
                      <MessageCircle className="h-6 w-6 text-green-600" />
                    </div>
                    <h4 className="text-sm font-medium mb-1">悬浮按钮</h4>
                    <p className="text-xs text-muted-foreground">添加悬浮聊天按钮</p>
                  </Label>
                </div>
              </RadioGroup>
            </div>
          </div>
          
          {embedType === 'link' && (
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
          )}
          
          {embedType === 'embed' && (
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
          )}
          
          {embedType === 'float' && (
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
          )}
        </div>
      </CardContent>
    </Card>
  )
}
