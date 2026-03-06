import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Globe, Lock, Trash2, Upload, Users } from 'lucide-react'

interface BotInfo {
  name: string
  description: string
  avatar: string
  category: string
  language: string
  visibility: string
  tags: string[]
}

interface BasicInfoProps {
  botInfo: BotInfo
  setBotInfo: (botInfo: BotInfo) => void
}

export function BasicInfo({ botInfo, setBotInfo }: BasicInfoProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>基本信息</CardTitle>
        <CardDescription>设置机器人的基本信息和展示方式</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start gap-4">
          <div className="relative">
            <Avatar className="h-24 w-24">
              <AvatarImage src={botInfo.avatar} alt={botInfo.name} />
              <AvatarFallback>{botInfo.name.slice(0, 2)}</AvatarFallback>
            </Avatar>
            <Button size="sm" variant="outline" className="absolute bottom-0 right-0 rounded-full p-1">
              <Upload className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex-1 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bot-name">机器人名称</Label>
                <Input
                  id="bot-name"
                  value={botInfo.name}
                  onChange={(e) => setBotInfo({ ...botInfo, name: e.target.value })}
                  placeholder="输入机器人名称"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bot-category">分类</Label>
                <Select 
                  value={botInfo.category} 
                  onValueChange={(value) => setBotInfo({ ...botInfo, category: value })}
                >
                  <SelectTrigger id="bot-category">
                    <SelectValue placeholder="选择分类" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="customer-service">客户服务</SelectItem>
                    <SelectItem value="marketing">营销助手</SelectItem>
                    <SelectItem value="knowledge-base">知识库</SelectItem>
                    <SelectItem value="assistant">个人助理</SelectItem>
                    <SelectItem value="other">其他</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="bot-description">机器人描述</Label>
              <Textarea
                id="bot-description"
                value={botInfo.description}
                onChange={(e) => setBotInfo({ ...botInfo, description: e.target.value })}
                placeholder="输入机器人描述"
                className="min-h-[80px]"
              />
            </div>
          </div>
        </div>
        
        <Separator />
        
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="bot-language">主要语言</Label>
            <Select 
              value={botInfo.language} 
              onValueChange={(value) => setBotInfo({ ...botInfo, language: value })}
            >
              <SelectTrigger id="bot-language">
                <SelectValue placeholder="选择语言" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="zh-CN">简体中文</SelectItem>
                <SelectItem value="en-US">英语</SelectItem>
                <SelectItem value="ja-JP">日语</SelectItem>
                <SelectItem value="ko-KR">韩语</SelectItem>
                <SelectItem value="multi">多语言</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="bot-visibility">可见性</Label>
            <Select 
              value={botInfo.visibility} 
              onValueChange={(value) => setBotInfo({ ...botInfo, visibility: value })}
            >
              <SelectTrigger id="bot-visibility">
                <SelectValue placeholder="选择可见性" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">
                  <div className="flex items-center">
                    <Lock className="mr-2 h-4 w-4" />
                    <span>仅创建者可见</span>
                  </div>
                </SelectItem>
                <SelectItem value="team">
                  <div className="flex items-center">
                    <Users className="mr-2 h-4 w-4" />
                    <span>团队可见</span>
                  </div>
                </SelectItem>
                <SelectItem value="public">
                  <div className="flex items-center">
                    <Globe className="mr-2 h-4 w-4" />
                    <span>公开</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="space-y-2">
          <Label htmlFor="bot-tags">标签</Label>
          <div className="flex flex-wrap gap-2">
            {botInfo.tags.map((tag, index) => (
              <Badge key={index} variant="secondary" className="flex items-center gap-1">
                {tag}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-4 w-4 p-0"
                  onClick={() => {
                    const newTags = [...botInfo.tags];
                    newTags.splice(index, 1);
                    setBotInfo({ ...botInfo, tags: newTags });
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </Badge>
            ))}
            <div className="flex items-center gap-2">
              <Input
                id="new-tag"
                placeholder="添加新标签"
                className="w-32"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                    setBotInfo({
                      ...botInfo,
                      tags: [...botInfo.tags, e.currentTarget.value.trim()]
                    });
                    e.currentTarget.value = '';
                  }
                }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
