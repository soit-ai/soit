import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Download, History, MoreHorizontal, Package, Tag } from 'lucide-react'
import type { Version } from './types'

interface VersionsTabProps {
  currentVersion: string;
  versions: Version[];
  getVersionStatusBadge: (status: string) => React.ReactNode;
}

export function VersionsTab({ currentVersion, versions, getVersionStatusBadge }: VersionsTabProps) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>当前版本</CardTitle>
          <CardDescription>查看和管理机器人的当前版本</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <Package className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{currentVersion}</h3>
                  <p className="text-sm text-muted-foreground">发布于 {versions[0].date}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {getVersionStatusBadge('current')}
                <Button variant="outline" size="sm">
                  <History className="h-4 w-4 mr-1" />
                  回滚
                </Button>
              </div>
            </div>
            
            <Separator className="my-4" />
            
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium mb-2">版本说明</h4>
                <p className="text-sm text-muted-foreground">{versions[0].changes}</p>
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <h4 className="text-sm font-medium mb-1">发布者</h4>
                  <div className="flex items-center">
                    <Avatar className="h-6 w-6 mr-2">
                      <AvatarFallback>{versions[0].author.charAt(0)}</AvatarFallback>
                    </Avatar>
                    <span className="text-sm">{versions[0].author}</span>
                  </div>
                </div>
                
                <div>
                  <h4 className="text-sm font-medium mb-1">部署次数</h4>
                  <p className="text-sm">{versions[0].deployments} 次</p>
                </div>
                
                <div>
                  <h4 className="text-sm font-medium mb-1">API 端点</h4>
                  <div className="flex items-center">
                    <code className="text-xs bg-muted px-1 py-0.5 rounded">/api/v1/bot/{'{id}'}</code>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader>
          <CardTitle>版本历史</CardTitle>
          <CardDescription>查看所有历史版本</CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px] rounded-md border">
            <div className="p-4 space-y-4">
              {versions.map((version, index) => (
                <div key={version.version} className="flex items-start p-4 rounded-lg border">
                  <div className="mr-4 mt-1">
                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                      <Tag className="h-4 w-4 text-primary" />
                    </div>
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center">
                        <h3 className="text-base font-semibold mr-2">{version.version}</h3>
                        {getVersionStatusBadge(version.status)}
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button variant="ghost" size="sm">
                          <Download className="h-4 w-4 mr-1" />
                          下载
                        </Button>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    
                    <p className="text-sm text-muted-foreground mb-2">{version.description}</p>
                    
                    <div className="flex items-center text-xs text-muted-foreground">
                      <span className="mr-3">发布于 {version.date}</span>
                      <span className="mr-3">作者: {version.author}</span>
                      <span>部署: {version.deployments} 次</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
        <CardFooter>
          <div className="flex justify-between items-center w-full">
            <div className="text-sm text-muted-foreground">
              共 {versions.length} 个版本
            </div>
            <Button variant="outline" size="sm">
              <History className="h-4 w-4 mr-1" />
              查看更多历史
            </Button>
          </div>
        </CardFooter>
      </Card>
    </>
  )
}
