import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Code, Copy, Database, ExternalLink, Info, Key, RefreshCw, Server, Terminal } from 'lucide-react'

interface ApiTabProps {
  apiStatus: string;
  onOpenApiKeyDialog: () => void;
}

export function ApiTab({ apiStatus, onOpenApiKeyDialog }: ApiTabProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>后端服务 API</CardTitle>
            <CardDescription>可集成到应用程序的后端服务</CardDescription>
          </div>
          <Badge className={`${apiStatus === '运行中' ? 'bg-green-500' : 'bg-yellow-500'}`}>
            {apiStatus}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="rounded-lg border p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-4">
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <Server className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="text-base font-semibold">API 访问端点</h3>
                  <p className="text-sm text-muted-foreground">用于集成到您的应用程序中</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" onClick={onOpenApiKeyDialog}>
                  <Key className="h-4 w-4 mr-1" />
                  API 密钥
                </Button>
                <Button variant="outline" size="sm">
                  <Terminal className="h-4 w-4 mr-1" />
                  查看文档
                </Button>
              </div>
            </div>
            
            <div className="flex items-center space-x-2 bg-muted p-2 rounded-md">
              <Input 
                readOnly 
                value="https://api.soit.ai/v1" 
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
                  <Database className="h-4 w-4 text-primary" />
                </div>
                <h3 className="text-sm font-medium">API 使用情况</h3>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm">请求总数</span>
                  <span className="text-sm font-medium">12,345</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">本月请求</span>
                  <span className="text-sm font-medium">2,456</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">平均响应时间</span>
                  <span className="text-sm font-medium">245ms</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">成功率</span>
                  <span className="text-sm font-medium">99.8%</span>
                </div>
              </div>
            </div>
            
            <div className="rounded-lg border p-4">
              <div className="flex items-center space-x-3 mb-3">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Server className="h-4 w-4 text-primary" />
                </div>
                <h3 className="text-sm font-medium">API 设置</h3>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="rate-limiting" className="text-sm">速率限制</Label>
                  <Switch id="rate-limiting" defaultChecked />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="cors-enabled" className="text-sm">CORS 支持</Label>
                  <Switch id="cors-enabled" defaultChecked />
                </div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="logging" className="text-sm">请求日志</Label>
                  <Switch id="logging" defaultChecked />
                </div>
              </div>
            </div>
          </div>
          
          <div className="rounded-lg border p-4">
            <div className="flex items-center space-x-3 mb-3">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Code className="h-4 w-4 text-primary" />
              </div>
              <h3 className="text-sm font-medium">代码示例</h3>
            </div>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <Label className="text-sm">cURL</Label>
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
                <pre className="bg-muted p-2 rounded-md text-xs overflow-x-auto">
                  {`curl -X POST https://api.soit.ai/v1/chat-messages \\
-H "Authorization: Bearer YOUR_API_KEY" \\
-H "Content-Type: application/json" \\
-d '{"messages":[{"role":"user","content":"Hello"}]}'`}
                </pre>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <Label className="text-sm">JavaScript</Label>
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
                <pre className="bg-muted p-2 rounded-md text-xs overflow-x-auto">
                  {`fetch('https://api.soit.ai/v1/chat-messages', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    messages: [{role: 'user', content: 'Hello'}]
  })
})`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center">
            <Info className="h-4 w-4 text-muted-foreground mr-1" />
            <span className="text-sm text-muted-foreground">API 版本: v1</span>
          </div>
          <Button>
            <RefreshCw className="h-4 w-4 mr-1" />
            重新部署 API
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
