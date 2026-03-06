import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Sparkles, Layers, Wand2, Copy, Check, Info, X, Zap, type LucideIcon } from 'lucide-react'
import { SelectModel } from '@/components/ui/form/select-model'
import { ModelOption, type ModelOptionValues } from '@/components/ui/form/model-option'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { promptList } from '@/data/prompt'

interface PromptTabProps {
  systemPrompt: string
  setSystemPrompt: (prompt: string) => void
}

// 提示词生成器模板类型
interface PromptTemplate {
  id: string;
  icon: LucideIcon;
  name: string;
  description: string;
}

// 预设的提示词生成器模板
const promptGeneratorTemplates: PromptTemplate[] = [
  {
    id: 'python-assistant',
    icon: Zap,
    name: 'Python 代码助手',
    description: '创建一个专业的Python编程助手，能够提供代码示例和解决方案'
  },
  {
    id: 'creative-writer',
    icon: Sparkles,
    name: '智能机器人',
    description: '创建一个通用的智能对话机器人，能够回答各种问题'
  },
  {
    id: 'meeting-summary',
    icon: Layers,
    name: '总结会议记要',
    description: '创建一个专门用于总结会议内容和提取关键点的助手'
  },
  {
    id: 'color-text',
    icon: Wand2,
    name: '润色文章',
    description: '创建一个能够改进和润色文章的助手，提升文章质量'
  },
  {
    id: 'business-analysis',
    icon: Info,
    name: '职业分析师',
    description: '创建一个专业的业务分析师，能够分析数据并提供见解'
  },
  {
    id: 'excel-expert',
    icon: Copy,
    name: 'Excel 公式专家',
    description: '创建一个Excel专家，能够解释和创建复杂的公式和数据分析'
  },
  {
    id: 'financial-advisor',
    icon: Check,
    name: '运行高级助手',
    description: '创建一个能够提供财务建议和分析的助手'
  },
  {
    id: 'sql-generator',
    icon: Layers,
    name: 'SQL 生成',
    description: '创建一个能够生成和优化SQL查询的助手'
  },
  {
    id: 'git-expert',
    icon: Zap,
    name: 'Git 大师',
    description: '创建一个Git专家，能够解释复杂的Git操作和工作流'
  }
];

export const PromptTab: React.FC<PromptTabProps> = ({
  systemPrompt,
  setSystemPrompt,
}) => {
  const [isGenerating, setIsGenerating] = useState(false)
  const [showTemplatePopover, setShowTemplatePopover] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [copiedPrompt, setCopiedPrompt] = useState<string | null>(null)
  const [showPromptGenerator, setShowPromptGenerator] = useState(false)
  const [generatorInput, setGeneratorInput] = useState('')
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)

  // 模拟生成提示词的函数
  const generatePrompt = () => {
    setIsGenerating(true)
    // 模拟API调用延迟
    setTimeout(() => {
      const generatedPrompt = `你是一个专业的AI助手，能够提供准确、有用的信息。你应该：
- 回答用户的问题
- 提供相关的建议
- 保持友好和专业的态度
- 在不确定的情况下承认自己的局限性
- 避免提供有害或误导性的信息`

      setSystemPrompt(generatedPrompt)
      setIsGenerating(false)
    }, 1500)
  }

  // 复制提示词模板
  const copyTemplate = (prompt: string) => {
    setSystemPrompt(prompt)
    setCopiedPrompt(prompt)
    setTimeout(() => setCopiedPrompt(null), 2000)
    setShowTemplatePopover(false)
  }

  // 过滤提示词模板
  const filteredPrompts = promptList.filter(prompt => {
    const matchesSearch = searchQuery === '' ||
      prompt.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prompt.description.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesTab = activeTab === 'all' || prompt.type === activeTab

    return matchesSearch && matchesTab
  })

  return (
    <div className="space-y-4">
      <Card className="border-2 border-primary/10 shadow-md">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl flex items-center gap-2">
                系统提示词
                <Badge variant="outline" className="ml-2 text-xs font-normal">
                  核心能力
                </Badge>
              </CardTitle>
              <CardDescription className="mt-1.5">
                定义助手的角色、行为和能力，是构建高质量AI助手的关键
              </CardDescription>
            </div>
            <div className="flex items-center space-x-1">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Info className="h-4 w-4" />
                <span className="sr-only">提示词编写指南</span>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Textarea
              placeholder="输入系统提示词，定义助手的行为模式..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={10}
              className="font-mono text-sm resize-y min-h-[200px] pr-4 border-primary/20 focus-visible:ring-primary/30"
            />
            <div className="absolute top-3 right-3 flex flex-col space-y-2">
              <Button variant="ghost" size="icon" className="h-7 w-7 bg-background/80 hover:bg-background">
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowPromptGenerator(true)}
                className="border-primary/20 hover:bg-primary/5 hover:text-primary"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                生成提示词
              </Button>

              <Popover open={showTemplatePopover} onOpenChange={setShowTemplatePopover}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-primary/20 hover:bg-primary/5 hover:text-primary"
                  >
                    <Layers className="mr-2 h-4 w-4" />
                    提示词模板
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[400px] p-0" align="start" sideOffset={5}>
                  <div className="p-4 border-b">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">提示词模板库</h3>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => setShowTemplatePopover(false)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                    <Input
                      placeholder="搜索模板..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="h-8"
                    />
                  </div>

                  <Tabs defaultValue="all" value={activeTab} onValueChange={setActiveTab}>
                    <div className="px-4 py-2 border-b">
                      <TabsList className="grid grid-cols-3 h-8">
                        <TabsTrigger value="all" className="text-xs">全部</TabsTrigger>
                        <TabsTrigger value="text" className="text-xs">通用</TabsTrigger>
                        <TabsTrigger value="code" className="text-xs">专业</TabsTrigger>
                      </TabsList>
                    </div>

                    <TabsContent value={activeTab} className="mt-0">
                      <ScrollArea className="h-[300px]">
                        <div className="p-4 space-y-3">
                          {filteredPrompts.length > 0 ? (
                            filteredPrompts.map((template) => (
                              <div
                                key={template.uuid}
                                className="border rounded-md p-3 hover:border-primary/30 hover:bg-primary/5 cursor-pointer transition-colors"
                                onClick={() => copyTemplate(template.prompt)}
                              >
                                <div className="flex items-center justify-between mb-1">
                                  <h4 className="font-medium text-sm">{template.name}</h4>
                                  <Button variant="ghost" size="icon" className="h-6 w-6">
                                    {copiedPrompt === template.prompt ? (
                                      <Check className="h-3.5 w-3.5 text-green-500" />
                                    ) : (
                                      <Copy className="h-3.5 w-3.5" />
                                    )}
                                  </Button>
                                </div>
                                <p className="text-xs text-muted-foreground line-clamp-2">{template.description}</p>
                              </div>
                            ))
                          ) : (
                            <div className="text-center py-8 text-muted-foreground">
                              <p>没有找到匹配的模板</p>
                            </div>
                          )}
                        </div>
                      </ScrollArea>
                    </TabsContent>
                  </Tabs>
                </PopoverContent>
              </Popover>
            </div>
            <div className="flex items-center space-x-2">
              <div className={cn(
                "px-2 py-1 rounded-md text-xs",
                systemPrompt.length > 2000 ? "bg-red-100 text-red-600" : "bg-muted text-muted-foreground"
              )}>
                {systemPrompt.length} / 4000 字符
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

    

      {/* 提示词生成器弹窗 */}
      <Dialog open={showPromptGenerator} onOpenChange={setShowPromptGenerator}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle className="text-xl">提示词生成器</DialogTitle>
            <DialogDescription>
              提示词生成器使用已配置的模型来优化提示词，以获得更好的结构。请写出清晰详细的说明。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 my-2">
            {/* 快速选择模板 */}
            <div>
              <Label className="text-sm font-medium mb-2 block">试一试</Label>
              <div className="grid grid-cols-3 gap-2">
                {promptGeneratorTemplates.slice(0, 9).map((template) => (
                  <Button
                    key={template.id}
                    variant="outline"
                    className={cn(
                      "h-auto py-2 px-3 justify-start text-left",
                      selectedTemplate === template.id && "border-primary bg-primary/5"
                    )}
                    onClick={() => {
                      setSelectedTemplate(template.id);
                      // 根据模板ID设置不同的预设输入
                      switch(template.id) {
                        case 'python-assistant':
                          setGeneratorInput('创建一个能够帮助用户编写和调试Python代码的助手');
                          break;
                        case 'creative-writer':
                          setGeneratorInput('创建一个通用的智能对话机器人，能够回答各种领域的问题');
                          break;
                        case 'meeting-summary':
                          setGeneratorInput('创建一个能够总结会议内容和提取关键点的助手');
                          break;
                        case 'color-text':
                          setGeneratorInput('创建一个能够改进和润色文章的助手');
                          break;
                        default:
                          setGeneratorInput(template.description);
                      }
                    }}
                  >
                    <template.icon className="h-4 w-4 mr-2 flex-shrink-0" />
                    <span className="text-xs">{template.name}</span>
                  </Button>
                ))}
              </div>
            </div>

            {/* 指令输入 */}
            <div>
              <Label htmlFor="prompt-instruction" className="text-sm font-medium mb-2 block">指令</Label>
              <Textarea
                id="prompt-instruction"
                placeholder="写下需求，具体的说明..."
                value={generatorInput}
                onChange={(e) => setGeneratorInput(e.target.value)}
                className="min-h-[120px] resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowPromptGenerator(false)}
              className="mr-2"
            >
              取消
            </Button>
            <Button
              onClick={() => {
                setIsGenerating(true);
                // 模拟生成过程
                setTimeout(() => {
                  // 根据选择的模板和输入生成提示词
                  const template = promptGeneratorTemplates.find(t => t.id === selectedTemplate);
                  let generatedPrompt = '';

                  if (template) {
                    switch (template.id) {
                      case 'python-assistant':
                        generatedPrompt = `你是一个专业的Python编程助手。你应该：
- 提供清晰、简洁的Python代码示例
- 解释代码的工作原理和最佳实践
- 帮助用户调试和优化他们的Python代码
- 推荐适当的库和工具
- 保持代码符合PEP 8风格指南`;
                        break;
                      case 'creative-writer':
                        generatedPrompt = `你是一个智能对话机器人，能够：
- 回答用户各种领域的问题
- 提供有用、准确的信息
- 保持对话友好和专业
- 在不确定时承认自己的局限性
- 避免提供有害或误导性的内容`;
                        break;
                      default:
                        generatedPrompt = `你是一个专业的AI助手，专注于${template.name}领域。你能够：
- 提供专业的${template.description}
- 回答用户的相关问题
- 提供清晰、有条理的信息
- 使用专业术语同时保持易于理解
- 在需要时提供进一步学习的资源`;
                    }
                  } else if (generatorInput) {
                    // 如果有用户输入但没有选择模板
                    generatedPrompt = `你是一个专业的AI助手，专注于${generatorInput}。你应该：
- 提供准确、有用的信息
- 回答用户的问题
- 保持友好和专业的态度
- 在不确定时承认自己的局限性
- 避免提供有害或误导性的内容`;
                  }

                  if (generatedPrompt) {
                    setSystemPrompt(generatedPrompt);
                    setShowPromptGenerator(false);
                  }

                  setIsGenerating(false);
                  setSelectedTemplate(null);
                  setGeneratorInput('');
                }, 1500);
              }}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <>
                  <Wand2 className="mr-2 h-4 w-4 animate-pulse" />
                  生成中...
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-4 w-4" />
                  生成
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}



export default PromptTab
