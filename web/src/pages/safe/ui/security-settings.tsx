import React, { useState, useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { 
  ShieldIcon, 
  KeyIcon, 
  LockIcon, 
  UserIcon,
  SaveIcon,
  RefreshCwIcon,
  AlertTriangleIcon,
  CheckIcon,
  XIcon,
  SettingsIcon
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { useNavLayout } from '@/components/layout/nav-layout'

interface SecuritySettingsProps {
  subTab?: string | null;
}

function BoxHeader({ title, description, onRefresh }: { title: string; description: string; onRefresh?: () => void }) {
  return (
    <div className="flex flex-1 justify-between">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      {onRefresh && (
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCwIcon className="h-4 w-4 mr-2" />
          刷新
        </Button>
      )}
    </div>
  )
}

export function SecuritySettings({ subTab = null }: SecuritySettingsProps) {
  const { t } = useTranslation()
  const [passwordLength, setPasswordLength] = useState(12)
  const [securityLevel, setSecurityLevel] = useState(80)
  const { setHeaderContent } = useNavLayout()
  
  // 设置头部内容
  useEffect(() => {
    setHeaderContent(
      <BoxHeader 
        title="安全设置" 
        description="配置系统安全相关设置" 
        onRefresh={() => {
          // 刷新数据的逻辑
          console.log('Refreshing security settings...')
        }}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  // 获取安全级别标签
  const getSecurityLevelBadge = (level: number) => {
    if (level >= 80) {
      return <Badge className="bg-green-500">高</Badge>
    } else if (level >= 50) {
      return <Badge className="bg-amber-500">中</Badge>
    } else {
      return <Badge className="bg-red-500">低</Badge>
    }
  }

  return (
    <div className="space-y-6">
      <Tabs defaultValue="general" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="general">通用安全</TabsTrigger>
          <TabsTrigger value="authentication">认证设置</TabsTrigger>
          <TabsTrigger value="encryption">加密设置</TabsTrigger>
          <TabsTrigger value="advanced">高级设置</TabsTrigger>
        </TabsList>
        
        <TabsContent value="general">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldIcon className="h-5 w-5 text-primary" />
                <CardTitle>通用安全设置</CardTitle>
              </div>
              <CardDescription>
                配置系统基本安全选项
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>启用安全模式</Label>
                    <p className="text-sm text-muted-foreground">开启全面安全保护</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>自动安全更新</Label>
                    <p className="text-sm text-muted-foreground">自动应用安全更新和补丁</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>安全警报通知</Label>
                    <p className="text-sm text-muted-foreground">当检测到安全威胁时发送通知</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>异常行为检测</Label>
                    <p className="text-sm text-muted-foreground">检测并报告异常用户行为</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>安全级别</Label>
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{securityLevel}%</span>
                      {getSecurityLevelBadge(securityLevel)}
                    </div>
                  </div>
                  <Slider
                    value={[securityLevel]}
                    min={0}
                    max={100}
                    step={10}
                    onValueChange={(value) => setSecurityLevel(value[0])}
                    className="w-full"
                  />
                  <p className="text-sm text-muted-foreground mt-2">
                    调整系统整体安全级别，级别越高保护越严格，但可能影响用户体验
                  </p>
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <h3 className="text-sm font-medium">安全状态</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="flex items-center gap-2 p-3 border rounded-md">
                    <div className="h-8 w-8 rounded-full bg-green-50 flex items-center justify-center">
                      <CheckIcon className="h-5 w-5 text-green-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">防火墙</p>
                      <p className="text-xs text-muted-foreground">已启用</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 p-3 border rounded-md">
                    <div className="h-8 w-8 rounded-full bg-green-50 flex items-center justify-center">
                      <CheckIcon className="h-5 w-5 text-green-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">入侵检测</p>
                      <p className="text-xs text-muted-foreground">已启用</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 p-3 border rounded-md">
                    <div className="h-8 w-8 rounded-full bg-red-50 flex items-center justify-center">
                      <XIcon className="h-5 w-5 text-red-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">安全扫描</p>
                      <p className="text-xs text-muted-foreground">7天未执行</p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end gap-2">
              <Button variant="outline">
                <RefreshCwIcon className="h-4 w-4 mr-2" />
                重置默认值
              </Button>
              <Button>
                <SaveIcon className="h-4 w-4 mr-2" />
                保存设置
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="authentication">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <KeyIcon className="h-5 w-5 text-primary" />
                <CardTitle>认证安全设置</CardTitle>
              </div>
              <CardDescription>
                配置用户认证和访问控制选项
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>双因素认证</Label>
                    <p className="text-sm text-muted-foreground">要求用户使用两种认证方式</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>密码复杂度检查</Label>
                    <p className="text-sm text-muted-foreground">强制使用复杂密码</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>定期密码更新</Label>
                    <p className="text-sm text-muted-foreground">要求用户定期更新密码</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>登录失败锁定</Label>
                    <p className="text-sm text-muted-foreground">多次登录失败后锁定账户</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>会话超时</Label>
                    <p className="text-sm text-muted-foreground">长时间不活动后自动登出</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>最小密码长度</Label>
                    <span className="text-sm">{passwordLength} 个字符</span>
                  </div>
                  <Slider
                    value={[passwordLength]}
                    min={8}
                    max={20}
                    step={1}
                    onValueChange={(value) => setPasswordLength(value[0])}
                    className="w-full"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="login-attempts" className="mb-2 block">
                      最大登录尝试次数
                    </Label>
                    <select
                      id="login-attempts"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      defaultValue="5"
                    >
                      <option value="3">3次</option>
                      <option value="5">5次</option>
                      <option value="10">10次</option>
                    </select>
                  </div>
                  
                  <div>
                    <Label htmlFor="session-timeout" className="mb-2 block">
                      会话超时时间
                    </Label>
                    <select
                      id="session-timeout"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      defaultValue="30"
                    >
                      <option value="15">15分钟</option>
                      <option value="30">30分钟</option>
                      <option value="60">60分钟</option>
                      <option value="120">2小时</option>
                    </select>
                  </div>
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end gap-2">
              <Button variant="outline">
                <RefreshCwIcon className="h-4 w-4 mr-2" />
                重置默认值
              </Button>
              <Button>
                <SaveIcon className="h-4 w-4 mr-2" />
                保存设置
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="encryption">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <LockIcon className="h-5 w-5 text-primary" />
                <CardTitle>加密设置</CardTitle>
              </div>
              <CardDescription>
                配置数据加密和传输安全选项
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>启用数据加密</Label>
                    <p className="text-sm text-muted-foreground">对存储的数据进行加密</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>传输层加密</Label>
                    <p className="text-sm text-muted-foreground">使用TLS/SSL加密数据传输</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>端到端加密</Label>
                    <p className="text-sm text-muted-foreground">启用端到端加密通信</p>
                  </div>
                  <Switch />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>密钥自动轮换</Label>
                    <p className="text-sm text-muted-foreground">定期自动更新加密密钥</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <h3 className="text-sm font-medium">加密算法设置</h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="encryption-algorithm" className="mb-2 block">
                      加密算法
                    </Label>
                    <select
                      id="encryption-algorithm"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      defaultValue="aes-256"
                    >
                      <option value="aes-256">AES-256</option>
                      <option value="aes-128">AES-128</option>
                      <option value="chacha20">ChaCha20</option>
                      <option value="twofish">Twofish</option>
                    </select>
                  </div>
                  
                  <div>
                    <Label htmlFor="key-rotation" className="mb-2 block">
                      密钥轮换周期
                    </Label>
                    <select
                      id="key-rotation"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      defaultValue="90"
                    >
                      <option value="30">30天</option>
                      <option value="60">60天</option>
                      <option value="90">90天</option>
                      <option value="180">180天</option>
                    </select>
                  </div>
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <h3 className="text-sm font-medium">证书管理</h3>
                
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>证书名称</TableHead>
                        <TableHead>过期时间</TableHead>
                        <TableHead>状态</TableHead>
                        <TableHead className="text-right">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow>
                        <TableCell className="font-medium">SSL证书</TableCell>
                        <TableCell>2025-12-31</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                            有效
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm">
                            更新
                          </Button>
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="font-medium">API证书</TableCell>
                        <TableCell>2025-10-15</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                            有效
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm">
                            更新
                          </Button>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </div>
                
                <Button variant="outline" size="sm">
                  添加证书
                </Button>
              </div>
            </CardContent>
            <CardFooter className="flex justify-end gap-2">
              <Button variant="outline">
                <RefreshCwIcon className="h-4 w-4 mr-2" />
                重置默认值
              </Button>
              <Button>
                <SaveIcon className="h-4 w-4 mr-2" />
                保存设置
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="advanced">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <SettingsIcon className="h-5 w-5 text-primary" />
                <CardTitle>高级安全设置</CardTitle>
              </div>
              <CardDescription>
                配置高级安全选项和功能
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>网络安全扫描</Label>
                    <p className="text-sm text-muted-foreground">定期扫描网络安全漏洞</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>沙箱执行</Label>
                    <p className="text-sm text-muted-foreground">在隔离环境中执行不受信任的代码</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>IP地理位置验证</Label>
                    <p className="text-sm text-muted-foreground">验证用户登录位置</p>
                  </div>
                  <Switch />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>安全日志审计</Label>
                    <p className="text-sm text-muted-foreground">记录并审计所有安全相关操作</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>自动安全响应</Label>
                    <p className="text-sm text-muted-foreground">自动响应安全事件和威胁</p>
                  </div>
                  <Switch />
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <h3 className="text-sm font-medium">安全备份设置</h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="backup-frequency" className="mb-2 block">
                      备份频率
                    </Label>
                    <select
                      id="backup-frequency"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      defaultValue="daily"
                    >
                      <option value="hourly">每小时</option>
                      <option value="daily">每天</option>
                      <option value="weekly">每周</option>
                      <option value="monthly">每月</option>
                    </select>
                  </div>
                  
                  <div>
                    <Label htmlFor="backup-retention" className="mb-2 block">
                      备份保留期
                    </Label>
                    <select
                      id="backup-retention"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      defaultValue="30"
                    >
                      <option value="7">7天</option>
                      <option value="30">30天</option>
                      <option value="90">90天</option>
                      <option value="365">365天</option>
                    </select>
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>加密备份</Label>
                    <p className="text-sm text-muted-foreground">对备份数据进行加密</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>
              
              <div className="space-y-4 pt-4 border-t">
                <h3 className="text-sm font-medium">安全警报阈值</h3>
                
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>登录失败阈值</Label>
                    <span className="text-sm">5次</span>
                  </div>
                  <Slider
                    defaultValue={[5]}
                    min={3}
                    max={10}
                    step={1}
                    className="w-full"
                  />
                </div>
                
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>异常行为阈值</Label>
                    <span className="text-sm">中等</span>
                  </div>
                  <Slider
                    defaultValue={[50]}
                    min={0}
                    max={100}
                    step={10}
                    className="w-full"
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <div>
                <Button variant="destructive">
                  <AlertTriangleIcon className="h-4 w-4 mr-2" />
                  重置所有安全设置
                </Button>
              </div>
              <div className="flex gap-2">
                <Button variant="outline">
                  <RefreshCwIcon className="h-4 w-4 mr-2" />
                  重置默认值
                </Button>
                <Button>
                  <SaveIcon className="h-4 w-4 mr-2" />
                  保存设置
                </Button>
              </div>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
