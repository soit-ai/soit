import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Key, User } from 'lucide-react'

export function AccessControl() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>访问控制</CardTitle>
        <CardDescription>管理哪些用户和团队可以访问此机器人</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">公开访问</Label>
              <p className="text-sm text-muted-foreground">允许所有人无需登录即可访问此机器人</p>
            </div>
            <Switch checked={false} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">团队访问</Label>
              <p className="text-sm text-muted-foreground">允许团队所有成员访问此机器人</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">允许分享</Label>
              <p className="text-sm text-muted-foreground">允许用户通过链接分享此机器人</p>
            </div>
            <Switch checked={true} />
          </div>
          
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base">密码保护</Label>
              <p className="text-sm text-muted-foreground">访问此机器人需要密码</p>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={false} />
              <Button variant="outline" size="sm" disabled>
                <Key className="mr-2 h-4 w-4" />
                设置密码
              </Button>
            </div>
          </div>
        </div>
        
        <Separator />
        
        <div className="space-y-2">
          <Label>特定用户访问</Label>
          <p className="text-sm text-muted-foreground">添加可以访问此机器人的特定用户</p>
          
          <div className="rounded-md border">
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar>
                    <AvatarImage src="/avatars/user-1.png" />
                    <AvatarFallback>ZL</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-medium">张三</p>
                    <p className="text-xs text-muted-foreground">zhang@example.com</p>
                  </div>
                </div>
                <Select defaultValue="admin">
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">管理员</SelectItem>
                    <SelectItem value="editor">编辑者</SelectItem>
                    <SelectItem value="viewer">查看者</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <Separator />
            
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar>
                    <AvatarImage src="/avatars/user-2.png" />
                    <AvatarFallback>LW</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-medium">李四</p>
                    <p className="text-xs text-muted-foreground">li@example.com</p>
                  </div>
                </div>
                <Select defaultValue="editor">
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">管理员</SelectItem>
                    <SelectItem value="editor">编辑者</SelectItem>
                    <SelectItem value="viewer">查看者</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          
          <Button variant="outline" className="mt-2 w-full">
            <User className="mr-2 h-4 w-4" />
            添加用户
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
