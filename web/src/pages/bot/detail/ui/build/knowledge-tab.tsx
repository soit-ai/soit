import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PlusCircle, Settings2, FileText, InfoIcon } from 'lucide-react'

interface KnowledgeTabProps {
  enableKnowledgeBase: boolean
  setEnableKnowledgeBase: (enabled: boolean) => void
  knowledgeBases: Array<{
    id: string,
    name: string,
    description: string,
    documentCount: number,
    lastUpdated: string
  }>
  selectedKnowledgeBases: string[]
  handleKnowledgeBaseSelect: (kbId: string) => void
  handleCreateKnowledgeBase: () => void
}

export const KnowledgeTab: React.FC<KnowledgeTabProps> = ({
  enableKnowledgeBase,
  setEnableKnowledgeBase,
  knowledgeBases,
  selectedKnowledgeBases,
  handleKnowledgeBaseSelect,
  handleCreateKnowledgeBase
}) => {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>知识库</CardTitle>
          <Switch 
            checked={enableKnowledgeBase} 
            onCheckedChange={setEnableKnowledgeBase} 
          />
        </div>
        <CardDescription>连接知识库，让助手能够回答特定领域的问题</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {enableKnowledgeBase ? (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-medium">已选择 {selectedKnowledgeBases.length} 个知识库</h3>
              <Button variant="outline" size="sm" onClick={handleCreateKnowledgeBase}>
                <PlusCircle className="mr-2 h-4 w-4" />
                创建知识库
              </Button>
            </div>
            
            <div className="rounded-md border">
              <div className="grid grid-cols-12 gap-2 p-2 bg-muted/50 font-medium text-sm">
                <div className="col-span-3">名称</div>
                <div className="col-span-5">描述</div>
                <div className="col-span-2">文档数</div>
                <div className="col-span-2">操作</div>
              </div>
              <ScrollArea className="h-[200px]">
                {knowledgeBases.length > 0 ? (
                  <div className="divide-y">
                    {knowledgeBases.map((kb) => (
                      <div key={kb.id} className="grid grid-cols-12 gap-2 p-2 hover:bg-muted/30 text-sm">
                        <div className="col-span-3 flex items-center">
                          <Switch 
                            checked={selectedKnowledgeBases.includes(kb.id)} 
                            onCheckedChange={() => handleKnowledgeBaseSelect(kb.id)}
                            className="mr-2"
                          />
                          {kb.name}
                        </div>
                        <div className="col-span-5 flex items-center">{kb.description}</div>
                        <div className="col-span-2 flex items-center">
                          <Badge variant="outline">{kb.documentCount} 文档</Badge>
                        </div>
                        <div className="col-span-2 flex items-center space-x-1">
                          <Button 
                            variant="ghost" 
                            size="icon"
                          >
                            <Settings2 className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                          >
                            <FileText className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center justify-center p-4 text-sm text-muted-foreground">
                    暂无知识库，请创建或导入知识库
                  </div>
                )}
              </ScrollArea>
            </div>
            
            {selectedKnowledgeBases.length > 0 && (
              <div className="rounded-md border p-4 bg-muted/30">
                <h4 className="font-medium mb-2">知识库检索设置</h4>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>检索方式</Label>
                      <Select defaultValue="hybrid">
                        <SelectTrigger>
                          <SelectValue placeholder="选择检索方式" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="semantic">语义检索</SelectItem>
                          <SelectItem value="keyword">关键词检索</SelectItem>
                          <SelectItem value="hybrid">混合检索</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>检索数量</Label>
                      <Select defaultValue="5">
                        <SelectTrigger>
                          <SelectValue placeholder="选择检索数量" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="3">3 条</SelectItem>
                          <SelectItem value="5">5 条</SelectItem>
                          <SelectItem value="10">10 条</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>相关度阈值</Label>
                      <span className="text-xs text-muted-foreground">0.7</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="1" 
                      step="0.1" 
                      defaultValue="0.7" 
                      className="w-full" 
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>低</span>
                      <span>高</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div className="rounded-md border p-4 bg-blue-50 dark:bg-blue-950/50">
              <div className="flex items-start space-x-2">
                <InfoIcon className="h-5 w-5 text-blue-500 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-700 dark:text-blue-300">知识库示例流程</h4>
                  <p className="text-sm text-blue-600 dark:text-blue-400 mt-1">
                    当用户询问"产品手册中关于规格的说明在哪里？"时，助手将：
                  </p>
                  <ol className="text-sm text-blue-600 dark:text-blue-400 mt-1 space-y-1 list-decimal list-inside">
                    <li>分析用户问题，确定需要从知识库中检索信息</li>
                    <li>从"产品手册"知识库中检索相关内容</li>
                    <li>找到最相关的文档片段（如"第3章: 产品规格"）</li>
                    <li>根据检索到的内容生成回答</li>
                    <li>在回答中引用知识库来源，确保信息准确性</li>
                  </ol>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center p-4">
            <p className="text-sm text-muted-foreground">启用知识库功能以添加知识源</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default KnowledgeTab
