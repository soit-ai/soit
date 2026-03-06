import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { SelectModel } from '@/components/ui/form/select-model'
import { ModelOption, type ModelOptionValues } from '@/components/ui/form/model-option'

interface BasicInfoProps {
  botName: string
  setBotName: (name: string) => void
  botDescription: string
  setBotDescription: (description: string) => void
  selectedModel: string
  handleModelChange: (model: string) => void
  modelOptions: ModelOptionValues
  handleModelOptionsChange: (options: ModelOptionValues) => void
}

export const BasicInfo: React.FC<BasicInfoProps> = ({
  botName,
  setBotName,
  botDescription,
  setBotDescription,
  selectedModel,
  handleModelChange,
  modelOptions,
  handleModelOptionsChange
}) => {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
          <CardDescription>设置助手的基本信息</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="bot-name">助手名称</Label>
            <Input
              id="bot-name"
              placeholder="输入助手名称"
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bot-description">助手描述</Label>
            <Textarea
              id="bot-description"
              placeholder="描述这个助手的功能和特点"
              value={botDescription}
              onChange={(e) => setBotDescription(e.target.value)}
              rows={3}
            />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>模型设置</CardTitle>
          <CardDescription>选择模型和调整参数</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>选择模型</Label>
            <div className="flex items-center space-x-2">
              <SelectModel
                value={selectedModel}
                onChange={handleModelChange}
                className="flex-1"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </>
  )
}

export default BasicInfo
