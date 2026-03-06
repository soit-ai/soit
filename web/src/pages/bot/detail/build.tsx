import React, { useState, useRef, useEffect } from 'react'
import { useTranslation } from '@/i18n'
import { useParams } from 'react-router'
import { useNavigate } from '@/hooks/use-navigate'
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable'
import { Globe, Sliders, Puzzle } from 'lucide-react'
import { PageHeader } from './ui/build/page-header'
import { ConfigSidebar } from './ui/build/config-sidebar'
import { ChatTest } from './ui/build/chat-test'
import type { Variable } from './ui/build/variables-tab'
import { VariableType, DEFAULT_VARIABLE } from './ui/build/variables-tab'
import { NavHeader } from '@/components/layout/nav-layout'
import { useNavLayout } from '@/components/layout/nav-layout'

interface BuildPage2Props {}

const BuildPage2: React.FC<BuildPage2Props> = () => {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const threadRef = useRef<HTMLDivElement | null>(null)

  const { setHeaderContent } = useNavLayout()

  // 设置头部内容
  useEffect(() => {
    setHeaderContent(<PageHeader id={id} title={botName} navigate={navigate} handleSave={handleSave} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent])

  // 状态管理
  const [activeTab, setActiveTab] = useState('basic')
  const [botName, setBotName] = useState('构建助手')
  const [botDescription, setBotDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [selectedModel, setSelectedModel] = useState<string>('gpt-4o')
  type ModelOptionValues = {
    temperature: number
    topP: number
    presencePenalty: number
    frequencyPenalty: number
    maxTokens: number
    responseFormat: string
  }

  const [modelOptions, setModelOptions] = useState<ModelOptionValues>({
    temperature: 0.7,
    topP: 1,
    presencePenalty: 0,
    frequencyPenalty: 0,
    maxTokens: 0,
    responseFormat: 'auto',
  })
  const [enableKnowledgeBase, setEnableKnowledgeBase] = useState(false)
  const [enableTools, setEnableTools] = useState(false)
  const [testMessage, setTestMessage] = useState('')
  const [testHistory, setTestHistory] = useState<Array<{ role: string; content: string }>>([])

  // 变量管理
  const [variables, setVariables] = useState<Variable[]>([])
  const [newVariable, setNewVariable] = useState<Variable>({ ...DEFAULT_VARIABLE })
  const [editingVariableIndex, setEditingVariableIndex] = useState<number | null>(null)

  // 知识库管理
  const [knowledgeBases, setKnowledgeBases] = useState<
    Array<{
      id: string
      name: string
      description: string
      documentCount: number
      lastUpdated: string
    }>
  >([
    {
      id: 'kb-1',
      name: '产品手册',
      description: '包含产品使用说明、常见问题和技术规格',
      documentCount: 15,
      lastUpdated: '2025-05-25',
    },
    {
      id: 'kb-2',
      name: '公司政策',
      description: '公司内部规章制度和流程文档',
      documentCount: 8,
      lastUpdated: '2025-05-20',
    },
  ])
  const [selectedKnowledgeBases, setSelectedKnowledgeBases] = useState<string[]>([])

  // 工具管理
  const [availableTools, setAvailableTools] = useState<
    Array<{
      id: string
      name: string
      description: string
      category: string
      icon: React.ReactNode
    }>
  >([
    {
      id: 'tool-1',
      name: '天气查询',
      description: '获取全球各地实时天气和预报信息',
      category: 'API',
      icon: <Globe className="h-5 w-5" />,
    },
    {
      id: 'tool-2',
      name: '计算器',
      description: '执行数学计算和公式求解',
      category: '内置工具',
      icon: <Sliders className="h-5 w-5" />,
    },
    {
      id: 'tool-3',
      name: '日程管理',
      description: '查询和管理用户日程安排',
      category: '插件',
      icon: <Puzzle className="h-5 w-5" />,
    },
  ])
  const [selectedTools, setSelectedTools] = useState<string[]>([])

  // 技能管理
  const [skills, setSkills] = useState<Record<SkillType, boolean>>({
    textToSpeech: false,
    speechToText: false,
    fileUpload: false,
    documentReference: false,
    imageGeneration: false,
    codeInterpreter: false,
    internetAccess: false,
    customization: false,
  })

  // 发送测试消息
  const handleSendTest = (message: string) => {
    if (!message.trim()) return

    // 添加用户消息到历史
    const newHistory = [...testHistory, { role: 'user', content: message }]
    setTestHistory(newHistory)

    // 模拟助手回复
    setTimeout(() => {
      let replyContent = `这是基于您的配置的模拟回复。\n\n`

      if (systemPrompt) {
        replyContent += `您的系统提示词是: ${systemPrompt}\n\n`
      } else {
        replyContent += `您还没有设置系统提示词。请在左侧的提示词选项卡中设置。\n\n`
      }

      if (selectedModel) {
        replyContent += `选择的模型: ${selectedModel}\n`

        if (modelOptions.temperature > 0) {
          replyContent += `温度设置: ${modelOptions.temperature}\n\n`
        }
      }

      // 知识库示例流程
      if (enableKnowledgeBase && selectedKnowledgeBases.length > 0) {
        replyContent += `已启用知识库功能。\n`
        replyContent += `检索到的相关文档:\n`

        // 模拟知识库检索结果
        if (message.toLowerCase().includes('产品') || message.toLowerCase().includes('手册')) {
          replyContent += `- 产品手册 > 第3章: 产品规格 (相关度: 0.92)\n`
          replyContent += `- 产品手册 > 常见问题解答 (相关度: 0.85)\n\n`
        } else if (message.toLowerCase().includes('公司') || message.toLowerCase().includes('政策')) {
          replyContent += `- 公司政策 > 员工手册 (相关度: 0.88)\n`
          replyContent += `- 公司政策 > 休假制度 (相关度: 0.76)\n\n`
        } else {
          replyContent += `- 未找到与问题高度相关的文档\n\n`
        }
      } else if (enableKnowledgeBase) {
        replyContent += `\n\n已启用知识库功能，但未选择任何知识库。\n\n`
      }

      // 工具示例流程
      if (enableTools && selectedTools.length > 0) {
        replyContent += `已启用工具功能。\n`

        // 模拟工具调用
        if (message.toLowerCase().includes('天气') || message.toLowerCase().includes('温度')) {
          replyContent += `调用工具: 天气查询\n`
          replyContent += `参数: { location: "默认位置", date: "今天" }\n`
          replyContent += `工具返回结果: { "weather": "晴朗", "temperature": "22°C", "humidity": "45%" }\n\n`
          replyContent += `根据天气查询结果，今天天气晴朗，气温22°C，湿度45%，是个不错的天气。\n`
        } else if (message.toLowerCase().includes('计算') || message.toLowerCase().includes('等于')) {
          replyContent += `调用工具: 计算器\n`
          replyContent += `参数: { expression: "从消息中提取的表达式" }\n`
          replyContent += `工具返回结果: { "result": "计算结果" }\n\n`
        } else if (message.toLowerCase().includes('日程') || message.toLowerCase().includes('安排')) {
          replyContent += `调用工具: 日程管理\n`
          replyContent += `参数: { action: "查询", date: "从消息中提取的日期" }\n`
          replyContent += `工具返回结果: { "events": ["上午9:00 会议", "下午2:00 面试"] }\n\n`
          replyContent += `您在提到的日期有以下安排：上午9:00的会议和下午2:00的面试。\n`
        } else {
          replyContent += `未触发任何工具调用。\n\n`
        }
      } else if (enableTools) {
        replyContent += `\n\n已启用工具功能，但未选择任何工具。\n\n`
      }

      const assistantReply = {
        role: 'assistant',
        content: replyContent,
      }
      setTestHistory([...newHistory, assistantReply])
    }, 1000)

    setTestMessage('')
  }

  // 添加变量
  const handleAddVariable = () => {
    if (!newVariable.key.trim()) return

    setVariables([...variables, { ...newVariable }])
    setNewVariable({ ...DEFAULT_VARIABLE })
  }

  // 编辑变量
  const handleEditVariable = (index: number) => {
    setNewVariable({ ...variables[index] })
    setEditingVariableIndex(index)
  }

  // 更新变量
  const handleUpdateVariable = () => {
    if (editingVariableIndex === null || !newVariable.key.trim()) return

    const updatedVariables = [...variables]
    updatedVariables[editingVariableIndex] = { ...newVariable }
    setVariables(updatedVariables)
    setNewVariable({ ...DEFAULT_VARIABLE })
    setEditingVariableIndex(null)
  }

  // 删除变量
  const handleDeleteVariable = (index: number) => {
    const updatedVariables = [...variables]
    updatedVariables.splice(index, 1)
    setVariables(updatedVariables)

    if (editingVariableIndex === index) {
      setNewVariable({ ...DEFAULT_VARIABLE })
      setEditingVariableIndex(null)
    }
  }

  // 取消编辑
  const handleCancelEdit = () => {
    setNewVariable({ ...DEFAULT_VARIABLE })
    setEditingVariableIndex(null)
  }

  type SkillType = 'textToSpeech' | 'speechToText' | 'fileUpload' | 'documentReference' | 'imageGeneration' | 'codeInterpreter' | 'internetAccess' | 'customization'

  // 技能开关切换
  const handleSkillToggle = (skill: keyof typeof skills) => {
    setSkills((prev) => ({
      ...prev,
      [skill]: !prev[skill],
    }))
  }

  // 保存
  const handleSave = () => {
    // 模拟保存操作
    console.log('Saving bot configuration:', {
      id,
      name: botName,
      description: botDescription,
      systemPrompt,
      model: selectedModel,
      modelOptions,
      enableKnowledgeBase,
      enableTools,
      variables,
      skills,
    })

    // 保存后跳转到详情页
    navigate(`/bot/${id || 'new'}`)
  }

  // 模型选择变更
  const handleModelChange = (model: string) => {
    setSelectedModel(model)
  }

  // 模型参数变更
  const handleModelOptionsChange = (options: ModelOptionValues) => {
    setModelOptions(options)
  }

  // 知识库选择处理
  const handleKnowledgeBaseSelect = (kbId: string) => {
    setSelectedKnowledgeBases((prev) => {
      if (prev.includes(kbId)) {
        return prev.filter((id) => id !== kbId)
      } else {
        return [...prev, kbId]
      }
    })
  }

  // 工具选择处理
  const handleToolSelect = (toolId: string) => {
    setSelectedTools((prev) => {
      if (prev.includes(toolId)) {
        return prev.filter((id) => id !== toolId)
      } else {
        return [...prev, toolId]
      }
    })
  }

  // 创建新知识库
  const handleCreateKnowledgeBase = () => {
    // 这里可以打开一个创建知识库的抽屉或模态框
    console.log('打开创建知识库界面')
  }

  // 创建新工具
  const handleCreateTool = () => {
    // 这里可以打开一个创建工具的抽屉或模态框
    console.log('打开创建工具界面')
  }

  return (
    <div className="flex flex-col h-full w-full">
      <ResizablePanelGroup direction="horizontal" className="flex-1">
        {/* 左侧配置面板 */}
        <ResizablePanel defaultSize={40} minSize={30} maxSize={60} className="border-r bg-background">
          <ConfigSidebar
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            botName={botName}
            setBotName={setBotName}
            botDescription={botDescription}
            setBotDescription={setBotDescription}
            systemPrompt={systemPrompt}
            setSystemPrompt={setSystemPrompt}
            selectedModel={selectedModel}
            handleModelChange={handleModelChange}
            modelOptions={modelOptions}
            handleModelOptionsChange={handleModelOptionsChange}
            variables={variables}
            newVariable={newVariable}
            setNewVariable={setNewVariable}
            editingVariableIndex={editingVariableIndex}
            handleAddVariable={handleAddVariable}
            handleEditVariable={handleEditVariable}
            handleUpdateVariable={handleUpdateVariable}
            handleDeleteVariable={handleDeleteVariable}
            handleCancelEdit={handleCancelEdit}
            skills={skills}
            handleSkillToggle={handleSkillToggle as any}
            enableKnowledgeBase={enableKnowledgeBase}
            setEnableKnowledgeBase={setEnableKnowledgeBase}
            knowledgeBases={knowledgeBases}
            selectedKnowledgeBases={selectedKnowledgeBases}
            handleKnowledgeBaseSelect={handleKnowledgeBaseSelect}
            handleCreateKnowledgeBase={handleCreateKnowledgeBase}
            enableTools={enableTools}
            setEnableTools={setEnableTools}
            availableTools={availableTools}
            selectedTools={selectedTools}
            handleToolSelect={handleToolSelect}
            handleCreateTool={handleCreateTool}
          />
        </ResizablePanel>

        <ResizableHandle />

        {/* 右侧测试面板 */}
        <ResizablePanel defaultSize={60} className="bg-background">
          <ChatTest testMessage={testMessage} setTestMessage={setTestMessage} testHistory={testHistory} handleSendTest={handleSendTest} />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

export default BuildPage2
