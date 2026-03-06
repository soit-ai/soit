import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { AlertCircle, Check, Code, ExternalLink, Globe, Info, RefreshCw, Share2, Terminal } from 'lucide-react'
import type { Deployment } from './types'

interface DeploymentsTabProps {
  deployments: Deployment[];
  currentVersion: string;
  getDeploymentStatusBadge: (status: string) => React.ReactNode;
}

export function DeploymentsTab({ deployments, currentVersion, getDeploymentStatusBadge }: DeploymentsTabProps) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>部署环境</CardTitle>
          <CardDescription>管理机器人的各个部署环境</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {deployments.map((deployment) => (
              <div key={deployment.id} className="rounded-lg border p-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-4">
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <Globe className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold">{deployment.environment || deployment.name}</h3>
                      <div className="flex items-center text-sm text-muted-foreground">
                        <code className="text-xs bg-muted px-1 py-0.5 rounded mr-2">{deployment.id}</code>
                        <span>流量: {deployment.traffic}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getDeploymentStatusBadge(deployment.status)}
                    <Button variant="outline" size="sm">
                      <Terminal className="h-4 w-4 mr-1" />
                      部署
                    </Button>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div>
                    <h4 className="text-sm font-medium mb-1">当前版本</h4>
                    <div className="flex items-center">
                      <Badge variant="outline" className="mr-1">{deployment.version}</Badge>
                      {deployment.version === currentVersion ? (
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">最新</Badge>
                      ) : (
                        <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">可更新</Badge>
                      )}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium mb-1">最后部署时间</h4>
                    <p className="text-sm">{deployment.lastDeployed}</p>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium mb-1">访问地址</h4>
                    <div className="flex items-center">
                      <a href={deployment.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline flex items-center">
                        {deployment.url.length > 30 ? `${deployment.url.substring(0, 30)}...` : deployment.url}
                        <ExternalLink className="h-3 w-3 ml-1" />
                      </a>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <Switch id={`auto-deploy-${deployment.id}`} />
                      <Label htmlFor={`auto-deploy-${deployment.id}`} className="text-sm">自动部署</Label>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <Switch id={`monitoring-${deployment.id}`} defaultChecked />
                      <Label htmlFor={`monitoring-${deployment.id}`} className="text-sm">启用监控</Label>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Button variant="ghost" size="sm">
                      <Share2 className="h-4 w-4 mr-1" />
                      分享
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Code className="h-4 w-4 mr-1" />
                      配置
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
        <CardFooter>
          <div className="flex justify-between items-center w-full">
            <div className="flex items-center">
              <Info className="h-4 w-4 text-muted-foreground mr-1" />
              <span className="text-sm text-muted-foreground">部署新环境需要管理员权限</span>
            </div>
            <Button>
              <Globe className="h-4 w-4 mr-1" />
              添加新环境
            </Button>
          </div>
        </CardFooter>
      </Card>
      
      <Card>
        <CardHeader>
          <CardTitle>部署配置</CardTitle>
          <CardDescription>配置部署参数和高级选项</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="webhook-url">Webhook URL</Label>
                <Input id="webhook-url" placeholder="https://example.com/webhook" />
                <p className="text-xs text-muted-foreground">部署完成后的通知 Webhook</p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="api-key">API 密钥</Label>
                <Input id="api-key" type="password" value="••••••••••••••••" />
                <p className="text-xs text-muted-foreground">用于部署和 API 访问的密钥</p>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="deploy-notes">部署说明</Label>
              <Textarea id="deploy-notes" placeholder="输入此次部署的说明信息" />
            </div>
            
            <div className="rounded-lg border p-4 bg-yellow-50">
              <div className="flex items-start">
                <AlertCircle className="h-5 w-5 text-yellow-600 mr-2 mt-0.5" />
                <div>
                  <h4 className="text-sm font-medium text-yellow-800">部署注意事项</h4>
                  <p className="text-sm text-yellow-700 mt-1">
                    部署到生产环境前，请确保已经在预发布环境进行了充分测试。部署过程中可能会导致短暂的服务不可用。
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <div className="flex justify-end space-x-2">
            <Button variant="outline">
              <RefreshCw className="h-4 w-4 mr-1" />
              重置
            </Button>
            <Button>
              <Check className="h-4 w-4 mr-1" />
              保存配置
            </Button>
          </div>
        </CardFooter>
      </Card>
    </>
  )
}
