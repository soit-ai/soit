import { useTranslation } from '@/i18n'
import { useState, useEffect } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/hooks/use-toast'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { MessageSquare, CheckCircle, AlertCircle, Clock, Filter, Search, Send, ThumbsUp } from 'lucide-react'

function IndexPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('submit')
  
  // 反馈表单状态
  const [feedbackForm, setFeedbackForm] = useState({
    title: '',
    type: 'bug',
    priority: 'medium',
    description: '',
    email: '',
    attachments: []
  })
  
  // 反馈列表
  const [feedbackList, setFeedbackList] = useState([
    {
      id: 'FB-001',
      title: '登录页面响应缓慢',
      type: 'performance',
      priority: 'high',
      status: 'in-progress',
      createdAt: '2025-05-28T10:30:00',
      updatedAt: '2025-05-30T14:20:00',
      submitter: 'user1@example.com'
    },
    {
      id: 'FB-002',
      title: '添加团队成员功能建议',
      type: 'feature',
      priority: 'medium',
      status: 'open',
      createdAt: '2025-05-29T09:15:00',
      updatedAt: '2025-05-29T09:15:00',
      submitter: 'user2@example.com'
    },
    {
      id: 'FB-003',
      title: '导出数据格式错误',
      type: 'bug',
      priority: 'high',
      status: 'resolved',
      createdAt: '2025-05-25T16:45:00',
      updatedAt: '2025-05-31T11:10:00',
      submitter: 'user3@example.com'
    },
    {
      id: 'FB-004',
      title: '移动端适配问题',
      type: 'bug',
      priority: 'medium',
      status: 'in-progress',
      createdAt: '2025-05-30T14:20:00',
      updatedAt: '2025-05-31T09:30:00',
      submitter: 'user1@example.com'
    },
    {
      id: 'FB-005',
      title: '集成第三方服务建议',
      type: 'feature',
      priority: 'low',
      status: 'open',
      createdAt: '2025-05-31T10:05:00',
      updatedAt: '2025-05-31T10:05:00',
      submitter: 'user4@example.com'
    }
  ])
  
  // 反馈统计数据
  const [feedbackStats, setFeedbackStats] = useState({
    total: 5,
    open: 2,
    inProgress: 2,
    resolved: 1,
    byType: {
      bug: 2,
      feature: 2,
      performance: 1,
      other: 0
    },
    byPriority: {
      high: 2,
      medium: 2,
      low: 1
    }
  })

  // 处理表单输入变化
  const handleInputChange = (field: string, value: string) => {
    setFeedbackForm(prev => ({
      ...prev,
      [field]: value
    }))
  }

  // 提交反馈
  const handleSubmitFeedback = () => {
    // 这里应该有API调用来提交反馈
    // 模拟提交成功
    toast({
      title: '反馈已提交',
      description: '感谢您的反馈，我们会尽快处理',
    })
    
    // 重置表单
    setFeedbackForm({
      title: '',
      type: 'bug',
      priority: 'medium',
      description: '',
      email: '',
      attachments: []
    })
  }

  // 获取状态对应的徽章颜色
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'open':
        return <Badge variant="outline">待处理</Badge>
      case 'in-progress':
        return <Badge variant="secondary">处理中</Badge>
      case 'resolved':
        return <Badge variant="success">已解决</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  // 获取类型对应的徽章
  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'bug':
        return <Badge variant="destructive">Bug</Badge>
      case 'feature':
        return <Badge variant="default">功能建议</Badge>
      case 'performance':
        return <Badge variant="warning">性能问题</Badge>
      default:
        return <Badge variant="outline">{type}</Badge>
    }
  }

  // 获取优先级对应的徽章
  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'high':
        return <Badge variant="destructive">高</Badge>
      case 'medium':
        return <Badge variant="warning">中</Badge>
      case 'low':
        return <Badge variant="secondary">低</Badge>
      default:
        return <Badge variant="outline">{priority}</Badge>
    }
  }

  // 格式化日期
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold tracking-tight">系统反馈</h3>
          <p className="text-sm text-muted-foreground">
            提交问题反馈或功能建议，帮助我们改进系统
          </p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="submit">提交反馈</TabsTrigger>
          <TabsTrigger value="list">反馈列表</TabsTrigger>
          <TabsTrigger value="stats">反馈统计</TabsTrigger>
        </TabsList>
        
        <TabsContent value="submit" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>提交新反馈</CardTitle>
              <CardDescription>
                请详细描述您遇到的问题或建议，以便我们更好地理解和处理
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="title">标题</Label>
                  <Input
                    id="title"
                    placeholder="简要描述问题或建议"
                    value={feedbackForm.title}
                    onChange={(e) => handleInputChange('title', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">联系邮箱</Label>
                  <Input
                    id="email"
                    placeholder="您的邮箱地址"
                    type="email"
                    value={feedbackForm.email}
                    onChange={(e) => handleInputChange('email', e.target.value)}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="type">反馈类型</Label>
                  <Select
                    value={feedbackForm.type}
                    onValueChange={(value) => handleInputChange('type', value)}
                  >
                    <SelectTrigger id="type">
                      <SelectValue placeholder="选择反馈类型" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bug">Bug报告</SelectItem>
                      <SelectItem value="feature">功能建议</SelectItem>
                      <SelectItem value="performance">性能问题</SelectItem>
                      <SelectItem value="other">其他</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="priority">优先级</Label>
                  <Select
                    value={feedbackForm.priority}
                    onValueChange={(value) => handleInputChange('priority', value)}
                  >
                    <SelectTrigger id="priority">
                      <SelectValue placeholder="选择优先级" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">高</SelectItem>
                      <SelectItem value="medium">中</SelectItem>
                      <SelectItem value="low">低</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="description">详细描述</Label>
                <Textarea
                  id="description"
                  placeholder="请详细描述您遇到的问题或建议..."
                  rows={5}
                  value={feedbackForm.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter>
              <Button onClick={handleSubmitFeedback}>
                <Send className="mr-2 h-4 w-4" />
                提交反馈
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="list" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>反馈列表</CardTitle>
              <CardDescription>
                查看所有已提交的反馈及其处理状态
              </CardDescription>
              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center space-x-2">
                  <Button variant="outline" size="sm">
                    <Filter className="mr-2 h-4 w-4" />
                    筛选
                  </Button>
                  <Select defaultValue="all">
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="状态筛选" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部状态</SelectItem>
                      <SelectItem value="open">待处理</SelectItem>
                      <SelectItem value="in-progress">处理中</SelectItem>
                      <SelectItem value="resolved">已解决</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="search"
                    placeholder="搜索反馈..."
                    className="w-[250px] pl-8"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>标题</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>优先级</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>提交时间</TableHead>
                    <TableHead>更新时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {feedbackList.map((feedback) => (
                    <TableRow key={feedback.id}>
                      <TableCell>{feedback.id}</TableCell>
                      <TableCell>{feedback.title}</TableCell>
                      <TableCell>{getTypeBadge(feedback.type)}</TableCell>
                      <TableCell>{getPriorityBadge(feedback.priority)}</TableCell>
                      <TableCell>{getStatusBadge(feedback.status)}</TableCell>
                      <TableCell>{formatDate(feedback.createdAt)}</TableCell>
                      <TableCell>{formatDate(feedback.updatedAt)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
            <CardFooter className="flex justify-between">
              <div className="text-sm text-muted-foreground">
                显示 {feedbackList.length} 条记录（共 {feedbackList.length} 条）
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" disabled>
                  上一页
                </Button>
                <Button variant="outline" size="sm" disabled>
                  下一页
                </Button>
              </div>
            </CardFooter>
          </Card>
        </TabsContent>
        
        <TabsContent value="stats" className="mt-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">总反馈数</CardTitle>
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{feedbackStats.total}</div>
                <p className="text-xs text-muted-foreground">所有已提交的反馈</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">待处理</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{feedbackStats.open}</div>
                <p className="text-xs text-muted-foreground">尚未开始处理的反馈</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">处理中</CardTitle>
                <AlertCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{feedbackStats.inProgress}</div>
                <p className="text-xs text-muted-foreground">正在处理的反馈</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">已解决</CardTitle>
                <CheckCircle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{feedbackStats.resolved}</div>
                <p className="text-xs text-muted-foreground">已成功解决的反馈</p>
              </CardContent>
            </Card>
          </div>
          
          <div className="grid gap-4 md:grid-cols-2 mt-4">
            <Card>
              <CardHeader>
                <CardTitle>按类型分布</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center">
                    <div className="w-16 text-sm">Bug</div>
                    <div className="flex-1">
                      <div className="bg-primary/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-primary h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byType.bug / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byType.bug}</div>
                  </div>
                  <div className="flex items-center">
                    <div className="w-16 text-sm">功能建议</div>
                    <div className="flex-1">
                      <div className="bg-primary/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-primary h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byType.feature / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byType.feature}</div>
                  </div>
                  <div className="flex items-center">
                    <div className="w-16 text-sm">性能问题</div>
                    <div className="flex-1">
                      <div className="bg-primary/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-primary h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byType.performance / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byType.performance}</div>
                  </div>
                  <div className="flex items-center">
                    <div className="w-16 text-sm">其他</div>
                    <div className="flex-1">
                      <div className="bg-primary/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-primary h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byType.other / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byType.other}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>按优先级分布</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center">
                    <div className="w-16 text-sm">高</div>
                    <div className="flex-1">
                      <div className="bg-destructive/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-destructive h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byPriority.high / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byPriority.high}</div>
                  </div>
                  <div className="flex items-center">
                    <div className="w-16 text-sm">中</div>
                    <div className="flex-1">
                      <div className="bg-warning/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-warning h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byPriority.medium / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byPriority.medium}</div>
                  </div>
                  <div className="flex items-center">
                    <div className="w-16 text-sm">低</div>
                    <div className="flex-1">
                      <div className="bg-secondary/10 h-3 w-full rounded-full overflow-hidden">
                        <div 
                          className="bg-secondary h-3 rounded-full" 
                          style={{ width: `${(feedbackStats.byPriority.low / feedbackStats.total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-10 text-right text-sm">{feedbackStats.byPriority.low}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default IndexPage
