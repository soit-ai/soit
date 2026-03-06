import React from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { Bot, RefreshCw, Sparkles, Layers, Zap, BrainCircuit, WrenchIcon } from 'lucide-react'
import BasicInfo from './basic-info'
import { PromptTab } from './prompt-tab'
import { VariablesTab } from './variables-tab'
import type { Variable } from './variables-tab'
import { SkillsTab } from './skills-tab'
import { KnowledgeTab } from './knowledge-tab'
import { ToolsTab } from './tools-tab'

interface ConfigSidebarProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  botName: string
  setBotName: (name: string) => void
  botDescription: string
  setBotDescription: (description: string) => void
  systemPrompt: string
  setSystemPrompt: (prompt: string) => void
  selectedModel: string
  handleModelChange: (model: string) => void
  modelOptions: any
  handleModelOptionsChange: (options: any) => void
  variables: Variable[]
  newVariable: Variable
  setNewVariable: (variable: Variable) => void
  editingVariableIndex: number | null
  handleAddVariable: () => void
  handleEditVariable: (index: number) => void
  handleUpdateVariable: () => void
  handleDeleteVariable: (index: number) => void
  handleCancelEdit: () => void
  skills: {
    textToSpeech: boolean
    speechToText: boolean
    fileUpload: boolean
    documentReference: boolean
    imageGeneration: boolean
    codeInterpreter: boolean
    internetAccess: boolean
    customization: boolean
  }
  handleSkillToggle: (skill: keyof typeof skills) => void
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
  enableTools: boolean
  setEnableTools: (enabled: boolean) => void
  availableTools: Array<{
    id: string,
    name: string,
    description: string,
    category: string,
    icon: React.ReactNode
  }>
  selectedTools: string[]
  handleToolSelect: (toolId: string) => void
  handleCreateTool: () => void
}

export const ConfigSidebar: React.FC<ConfigSidebarProps> = ({
  activeTab,
  setActiveTab,
  botName,
  setBotName,
  botDescription,
  setBotDescription,
  systemPrompt,
  setSystemPrompt,
  selectedModel,
  handleModelChange,
  modelOptions,
  handleModelOptionsChange,
  variables,
  newVariable,
  setNewVariable,
  editingVariableIndex,
  handleAddVariable,
  handleEditVariable,
  handleUpdateVariable,
  handleDeleteVariable,
  handleCancelEdit,
  skills,
  handleSkillToggle,
  enableKnowledgeBase,
  setEnableKnowledgeBase,
  knowledgeBases,
  selectedKnowledgeBases,
  handleKnowledgeBaseSelect,
  handleCreateKnowledgeBase,
  enableTools,
  setEnableTools,
  availableTools,
  selectedTools,
  handleToolSelect,
  handleCreateTool
}) => {
  return (
    <div className="flex flex-col h-full">

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          <PromptTab
            systemPrompt={systemPrompt}
            setSystemPrompt={setSystemPrompt}
            selectedModel={selectedModel}
            handleModelChange={handleModelChange}
            modelOptions={modelOptions}
            handleModelOptionsChange={handleModelOptionsChange}
          />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="basic">
                <Sparkles className="h-4 w-4 mr-2" />
                基本信息
              </TabsTrigger>
              <TabsTrigger value="variables">
                <Layers className="h-4 w-4 mr-2" />
                变量
              </TabsTrigger>
              <TabsTrigger value="skills">
                <Zap className="h-4 w-4 mr-2" />
                技能
              </TabsTrigger>
              <TabsTrigger value="knowledge">
                <BrainCircuit className="h-4 w-4 mr-2" />
                知识库
              </TabsTrigger>
              <TabsTrigger value="tools">
                <WrenchIcon className="h-4 w-4 mr-2" />
                工具
              </TabsTrigger>
            </TabsList>

            <TabsContent value="basic" className="space-y-4">
              <BasicInfo
                botName={botName}
                setBotName={setBotName}
                botDescription={botDescription}
                setBotDescription={setBotDescription}
              />

            </TabsContent>

            <TabsContent value="variables" className="space-y-4">
              <VariablesTab
                variables={variables}
                newVariable={newVariable}
                setNewVariable={setNewVariable}
                editingVariableIndex={editingVariableIndex}
                handleAddVariable={handleAddVariable}
                handleEditVariable={handleEditVariable}
                handleUpdateVariable={handleUpdateVariable}
                handleDeleteVariable={handleDeleteVariable}
                handleCancelEdit={handleCancelEdit}
              />
            </TabsContent>

            <TabsContent value="skills" className="space-y-4">
              <SkillsTab
                skills={skills}
                handleSkillToggle={handleSkillToggle}
              />
            </TabsContent>

            <TabsContent value="knowledge" className="space-y-4">
              <KnowledgeTab
                enableKnowledgeBase={enableKnowledgeBase}
                setEnableKnowledgeBase={setEnableKnowledgeBase}
                knowledgeBases={knowledgeBases}
                selectedKnowledgeBases={selectedKnowledgeBases}
                handleKnowledgeBaseSelect={handleKnowledgeBaseSelect}
                handleCreateKnowledgeBase={handleCreateKnowledgeBase}
              />
            </TabsContent>

            <TabsContent value="tools" className="space-y-4">
              <ToolsTab
                enableTools={enableTools}
                setEnableTools={setEnableTools}
                availableTools={availableTools}
                selectedTools={selectedTools}
                handleToolSelect={handleToolSelect}
                handleCreateTool={handleCreateTool}
              />
            </TabsContent>
          </Tabs>
        </div>
      </ScrollArea>
    </div>
  )
}

export default ConfigSidebar
