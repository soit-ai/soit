import { useTranslation } from '@/i18n'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Codebox } from '@/components/ui/codebox'
import { PageHeader, WebAppTab, ApiTab, VersionsTab, DeploymentsTab, ApiKeyDialog, EmbedCodeTab } from './ui/publish'
import type { Version, Deployment } from './ui/publish'
import { useNavLayout } from '@/components/layout/nav-layout'

function PublishNew() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState('web')
  const [isPublishing, setIsPublishing] = useState(false)
  const [publishVersion, setPublishVersion] = useState('latest')
  const [currentVersion, setCurrentVersion] = useState('v1.2.0')
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false)
  const [embedType, setEmbedType] = useState('link')
  const [apiKey, setApiKey] = useState('')
  const [webAppStatus, setWebAppStatus] = useState('运行中')
  const [apiStatus, setApiStatus] = useState('运行中')
  const [versions, setVersions] = useState<Version[]>([
    {
      version: 'v1.2.0',
      date: '2023-10-20',
      author: '张三',
      status: '已发布',
      description: '添加了新的聊天界面和改进了响应速度',
      changes: '添加了新的聊天界面和改进了响应速度',
      deployments: 5,
    },
    {
      version: 'v1.1.0',
      date: '2023-09-15',
      author: '李四',
      status: '已发布',
      description: '修复了若干bug并优化了性能',
      changes: '修复了若干bug并优化了性能',
      deployments: 3,
    },
    {
      version: 'v1.0.0',
      date: '2023-08-01',
      author: '王五',
      status: '已发布',
      description: '首次发布版本',
      changes: '首次发布版本',
      deployments: 2,
    },
  ])
  const [deployments, setDeployments] = useState<Deployment[]>([
    {
      id: 'prod-env',
      environment: '生产环境',
      name: '生产环境',
      status: '运行中',
      version: 'v1.2.0',
      lastDeployed: '2023-10-20 14:30',
      url: 'https://prod.example.com/bot',
      traffic: '85%',
    },
    {
      id: 'test-env',
      environment: '测试环境',
      name: '测试环境',
      status: '运行中',
      version: 'v1.2.0',
      lastDeployed: '2023-10-19 10:15',
      url: 'https://test.example.com/bot',
      traffic: '10%',
    },
    {
      id: 'dev-env',
      environment: '开发环境',
      name: '开发环境',
      status: '运行中',
      version: 'v1.2.0',
      lastDeployed: '2023-10-18 09:45',
      url: 'https://dev.example.com/bot',
      traffic: '5%',
    },
  ])

  const { setHeaderContent } = useNavLayout()

  // 设置头部内容
  useEffect(() => {
    setHeaderContent(<PageHeader isPublishing={isPublishing} onPublish={handlePublish} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  // 处理发布操作
  const handlePublish = () => {
    setIsPublishing(true)
    // 模拟发布过程
    setTimeout(() => {
      setIsPublishing(false)
      // 更新版本信息
      const newVersion = {
        version: 'v1.3.0',
        date: '2025-06-01',
        author: '当前用户',
        status: '已发布',
        description: '新版本发布',
        changes: '功能优化和bug修复',
        deployments: 0,
      }
      setVersions([newVersion, ...versions])
      setCurrentVersion('v1.3.0')
    }, 2000)
  }

  // 获取版本状态标签样式
  const getVersionStatusBadge = (status: string) => {
    switch (status) {
      case '已发布':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            已发布
          </Badge>
        )
      case '草稿':
        return (
          <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">
            草稿
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  // 获取部署状态标签样式
  const getDeploymentStatusBadge = (status: string) => {
    switch (status) {
      case '运行中':
        return <Badge className="bg-green-500">运行中</Badge>
      case '部署中':
        return <Badge className="bg-blue-500">部署中</Badge>
      case '失败':
        return <Badge className="bg-red-500">失败</Badge>
      default:
        return <Badge>{status}</Badge>
    }
  }

  // 处理API密钥生成
  const handleGenerateApiKey = () => {
    // 模拟生成API密钥
    const newApiKey = 'sk-' + Math.random().toString(36).substring(2, 15)
    setApiKey(newApiKey)
    setShowApiKeyDialog(true)
  }

  // 处理新建部署
  const handleCreateDeployment = (environment: string) => {
    // 模拟创建新部署
    const newDeployment = {
      id: `${environment.toLowerCase()}-${Date.now()}`,
      environment: environment,
      name: `${environment}`,
      status: '部署中',
      version: currentVersion,
      lastDeployed: new Date().toLocaleString(),
      url: `https://${environment.toLowerCase()}.example.com/bot`,
      traffic: '0%',
    }
    setDeployments([newDeployment, ...deployments])

    // 模拟部署完成
    setTimeout(() => {
      const updatedDeployments = deployments.map((dep) => {
        if (dep.id === newDeployment.id) {
          return { ...dep, status: '运行中' }
        }
        return dep
      })
      setDeployments(updatedDeployments)
    }, 3000)
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Tabs defaultValue="web" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
          <TabsList className="w-full md:w-auto grid grid-cols-4 md:flex">
            <TabsTrigger value="web">Web 应用</TabsTrigger>
            <TabsTrigger value="api">后端服务 API</TabsTrigger>
            <TabsTrigger value="versions">版本历史</TabsTrigger>
            <TabsTrigger value="deployments">部署</TabsTrigger>
          </TabsList>

          {/* 右侧空间保留，便于后续添加搜索或筛选功能 */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            <Select defaultValue="latest" value={publishVersion} onValueChange={setPublishVersion}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="选择版本" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="latest">最新版本</SelectItem>
                <SelectItem value="stable">稳定版本</SelectItem>
                <SelectItem value="custom">自定义版本</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <TabsContent value="web" className="mt-4 space-y-4">
          <WebAppTab webAppStatus={webAppStatus} onOpenEmbedDialog={() => {}} />
        </TabsContent>

        <TabsContent value="api" className="mt-4 space-y-4">
          <ApiTab apiStatus={apiStatus} onOpenApiKeyDialog={handleGenerateApiKey} />

          <div className="mt-6">
            <h3 className="text-lg font-medium mb-2">API 调用示例</h3>
            <Codebox
              language="javascript"
              code={`// 使用API密钥调用机器人
const response = await fetch('https://api.example.com/bot/${id}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ${apiKey || 'YOUR_API_KEY'}'
  },
  body: JSON.stringify({
    message: '你好，我有个问题想请教你',
    conversation_id: '123456789'
  })
});

const data = await response.json();
console.log(data);`}
              showLineNumbers={true}
              className="mb-4"
            />

            <h3 className="text-lg font-medium mb-2">响应格式</h3>
            <Codebox
              language="json"
              code={`{
  "id": "resp_123456789",
  "conversation_id": "123456789",
  "response": "你好！很高兴为你解答问题。请问有什么我可以帮助你的？",
  "created_at": "2025-06-01T11:08:56.000Z",
  "model": "gpt-4",
  "usage": {
    "prompt_tokens": 24,
    "completion_tokens": 32,
    "total_tokens": 56
  }
}`}
              showLineNumbers={true}
            />
          </div>
        </TabsContent>

        <TabsContent value="versions" className="mt-4 space-y-4">
          <VersionsTab currentVersion={currentVersion} versions={versions} getVersionStatusBadge={getVersionStatusBadge} />
        </TabsContent>

        <TabsContent value="deployments" className="mt-4 space-y-4">
          <DeploymentsTab deployments={deployments} currentVersion={currentVersion} getDeploymentStatusBadge={getDeploymentStatusBadge} />
        </TabsContent>
      </Tabs>

      {/* 对话框组件 */}
      <ApiKeyDialog open={showApiKeyDialog} onOpenChange={setShowApiKeyDialog} apiKey={apiKey} />
    </div>
  )
}

export default PublishNew
