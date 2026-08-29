import * as React from 'react'
import { useState, useEffect } from 'react'
import { Check, ChevronDown } from 'lucide-react'

import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ModelOption } from './model-option'

export type ModelType = 'llm' | 'chat' | 'vision' | 'text-embedding' | 'rerank' | 'speech2text' | 'tts' | 'moderation'

export interface ModelProps {
  id: string
  label: string
  value: string
  type: ModelType
  provider?: string
  /** Human-readable provider name shown as the group heading; `provider` stays the routing slug. */
  providerName?: string
  tags?: string[]
  capabilities?: string[]
  contextSize?: number
  isDefault?: boolean
}

interface SelectModelProps {
  value?: string
  onChange?: (value: string) => void
  models?: ModelProps[]
  placeholder?: string
  disabled?: boolean
  className?: string
  triggerClassName?: string
  contentClassName?: string
  showSearch?: boolean
  defaultOpen?: boolean
}

// Sample models for preview.
const _models: ModelProps[] = [
  {
    id: '1',
    label: 'gpt-4o',
    value: 'gpt-4o',
    type: 'chat',
    provider: 'OpenAI',
    tags: ['new'],
    contextSize: 128000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal', 'toolCalling'],
    isDefault: true,
  },
  {
    id: '2',
    label: 'gpt-4',
    value: 'gpt-4',
    type: 'chat',
    provider: 'OpenAI',
    contextSize: 8192,
    capabilities: ['textGeneration', 'codeGeneration'],
  },
  {
    id: '3',
    label: 'gpt-3.5-turbo',
    value: 'gpt-3.5-turbo',
    type: 'chat',
    provider: 'OpenAI',
    contextSize: 16385,
    capabilities: ['textGeneration', 'codeGeneration'],
  },
  {
    id: '4',
    label: 'gpt-3.5-turbo-0125',
    value: 'gpt-3.5-turbo-0125',
    type: 'chat',
    provider: 'OpenAI',
    contextSize: 16385,
    capabilities: ['textGeneration', 'codeGeneration'],
  },
  {
    id: '5',
    label: 'gpt-3.5-turbo-1106',
    value: 'gpt-3.5-turbo-1106',
    type: 'chat',
    provider: 'OpenAI',
    contextSize: 16385,
    capabilities: ['textGeneration', 'codeGeneration'],
  },
  {
    id: '6',
    label: 'gpt-3.5-turbo-instruct',
    value: 'gpt-3.5-turbo-instruct',
    type: 'chat',
    provider: 'OpenAI',
    contextSize: 4096,
    capabilities: ['textGeneration'],
  },
  {
    id: '7',
    label: 'chatgpt-4o-latest',
    value: 'chatgpt-4o-latest',
    type: 'chat',
    provider: 'OpenAI',
    tags: ['new'],
    contextSize: 128000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal', 'toolCalling'],
  },
  {
    id: '8',
    label: 'gpt-4o-mini-2024-07-18',
    value: 'gpt-4o-mini-2024-07-18',
    type: 'chat',
    provider: 'OpenAI',
    tags: ['new'],
    contextSize: 128000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal'],
  },
  {
    id: '9',
    label: 'gpt-4o-mini',
    value: 'gpt-4o-mini',
    type: 'chat',
    provider: 'OpenAI',
    contextSize: 128000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal'],
  },
  {
    id: '10',
    label: 'Claude Opus 4.8',
    value: 'claude-opus-4-8',
    type: 'chat',
    provider: 'Claude / Anthropic',
    contextSize: 1000000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal'],
    tags: ['premium'],
  },
  {
    id: '11',
    label: 'Claude Sonnet 4.6',
    value: 'claude-sonnet-4-6',
    type: 'chat',
    provider: 'Claude / Anthropic',
    contextSize: 1000000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal'],
  },
  {
    id: '12',
    label: 'Claude Haiku 4.5',
    value: 'claude-haiku-4-5-20251001',
    type: 'chat',
    provider: 'Claude / Anthropic',
    contextSize: 200000,
    capabilities: ['textGeneration', 'codeGeneration', 'multimodal'],
  },
]

function SelectModel({
  value,
  onChange,
  models = _models,
  placeholder,
  disabled = false,
  className,
  triggerClassName,
  contentClassName,
  showSearch = true,
  defaultOpen = false,
}: SelectModelProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedModel, setSelectedModel] = useState<ModelProps | undefined>(
    models?.find((model) => model.value === value)
  )
  const placeholderText = placeholder ?? t('common.model.selector.placeholder')
  const searchPlaceholder = t('common.model.selector.searchPlaceholder')
  const emptyText = t('common.model.selector.empty')
  const newTagLabel = t('common.model.selector.tag.new')

  useEffect(() => {
    setSelectedModel(models?.find((model) => model.value === value))
  }, [value, models])

  const filteredModels = searchQuery
    ? models?.filter(
        (model) =>
          model.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          model.value.toLowerCase().includes(searchQuery.toLowerCase()) ||
          model.provider?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          model.tags?.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : models

  const groupedModels: Record<string, ModelProps[]> = {}
  filteredModels?.forEach((model) => {
    const provider = model.provider || t('common.model.selector.providerOther')
    if (!groupedModels[provider]) {
      groupedModels[provider] = []
    }
    groupedModels[provider].push(model)
  })

  const handleSelect = (model: ModelProps) => {
    setSelectedModel(model)
    onChange?.(model.value)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className={cn('flex flex-1 w-full flex-row justify-between items-center gap-2', className)}>
        <PopoverTrigger render={<Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn('flex-1 justify-between', selectedModel && 'text-left', triggerClassName)}
          >
            {selectedModel ? (
              <HoverCard>
                <HoverCardTrigger delay={0} closeDelay={0} render={<div className="flex items-center gap-2 truncate cursor-pointer">
                    <ModelIcon type={selectedModel.type} />
                    <span className="truncate">{selectedModel.label}</span>
                    {selectedModel.tags?.includes('new') && (
                      <Badge variant="outline" className="ml-2 py-0 h-5">
                        {newTagLabel}
                      </Badge>
                    )}
                  </div>} />
                <HoverCardContent className="w-80 p-4" side="right" align="start" sideOffset={10}>
                  <ModelInfoCard model={selectedModel} />
                </HoverCardContent>
              </HoverCard>
            ) : (
              <span className="text-muted-foreground">{placeholderText}</span>
            )}

            <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>} />
        <ModelOption modelId={selectedModel?.value} className={cn('', triggerClassName)} />
      </div>
      <PopoverContent
        className={cn('p-0 w-full', contentClassName)}
        style={{ width: 'var(--radix-popover-trigger-width)', minWidth: '240px' }}
      >
        <Command className={cn('p-0 w-full')}>
          {showSearch && (
            <CommandInput
              placeholder={searchPlaceholder}
              value={searchQuery}
              onValueChange={setSearchQuery}
              className="h-9"
            />
          )}
          <ScrollArea className="h-[300px] flex flex-col">
            <CommandList className="h-full flex flex-col" style={{ scrollbarWidth: 'none' }}>
              <CommandEmpty>{emptyText}</CommandEmpty>
              {Object.entries(groupedModels).map(([provider, providerModels]) => (
                <CommandGroup key={provider} heading={providerModels[0]?.providerName || provider}>
                  {providerModels.map((model) => (
                    <CommandItem
                      key={model.value}
                      value={model.value}
                      onSelect={() => handleSelect(model)}
                      className="flex items-center justify-between py-2"
                    >
                      <HoverCard>
                        <HoverCardTrigger delay={0} closeDelay={0} render={<div className="flex items-center gap-2 cursor-pointer">
                            <ModelIcon type={model.type} />
                            <span>{model.label}</span>
                            {model.tags?.includes('new') && (
                              <Badge variant="outline" className="ml-2 py-0 h-5">
                                {newTagLabel}
                              </Badge>
                            )}
                          </div>} />
                        <HoverCardContent className="w-80 p-4" side="right" align="start" sideOffset={10}>
                          <ModelInfoCard model={model} />
                        </HoverCardContent>
                      </HoverCard>
                      {model.value === selectedModel?.value && <Check className="h-4 w-4 text-primary" />}
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}
            </CommandList>
          </ScrollArea>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function ModelIcon({ type }: { type: ModelType }) {
  const getIconColor = () => {
    switch (type) {
      case 'llm':
      case 'chat':
        return 'text-cat-blue bg-cat-blue/12'
      case 'vision':
        return 'text-cat-purple bg-cat-purple/12'
      case 'text-embedding':
        return 'text-cat-green bg-cat-green/12'
      case 'rerank':
        return 'text-cat-amber bg-cat-amber/12'
      case 'speech2text':
        return 'text-cat-amber bg-cat-amber/12'
      case 'tts':
        return 'text-cat-pink bg-cat-pink/12'
      case 'moderation':
        return 'text-cat-red bg-cat-red/12'
      default:
        return 'text-cat-slate bg-cat-slate/12'
    }
  }

  return <div className={cn('w-5 h-5 rounded-sm flex items-center justify-center', getIconColor())}>{type.charAt(0).toUpperCase()}</div>
}

function ModelInfoCard({ model }: { model: ModelProps }) {
  const { t, i18n } = useTranslation()

  const getModelTypeLabel = (type: ModelType) => {
    const typeLabels: Record<ModelType, string> = {
      llm: t('common.model.selector.type.llm'),
      chat: t('common.model.selector.type.chat'),
      vision: t('common.model.selector.type.vision'),
      'text-embedding': t('common.model.selector.type.textEmbedding'),
      rerank: t('common.model.selector.type.rerank'),
      speech2text: t('common.model.selector.type.speech2text'),
      tts: t('common.model.selector.type.tts'),
      moderation: t('common.model.selector.type.moderation'),
    }
    return typeLabels[type] || type
  }

  const getCapabilityLabel = (capability: string) => {
    const capabilityKeys: Record<string, string> = {
      textGeneration: 'textGeneration',
      codeGeneration: 'codeGeneration',
      multimodal: 'multimodal',
      toolCalling: 'toolCalling',
    }
    const key = capabilityKeys[capability]
    return key ? t(`common.model.selector.capability.${key}` as TranslationKey) : capability
  }

  const getTagLabel = (tag: string) => {
    const tagKeys: Record<string, string> = {
      new: 'new',
      premium: 'premium',
    }
    const key = tagKeys[tag]
    return key ? t(`common.model.selector.tag.${key}` as TranslationKey) : tag
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-sm font-semibold">{model.label}</h4>
          <p className="text-xs text-muted-foreground">{model.value}</p>
        </div>
        <ModelIcon type={model.type} />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="space-y-1">
          <p className="text-muted-foreground">{t('common.model.selector.labels.provider')}</p>
          <p>{model.provider || t('common.model.selector.providerUnknown')}</p>
        </div>
        <div className="space-y-1">
          <p className="text-muted-foreground">{t('common.model.selector.labels.type')}</p>
          <p>{getModelTypeLabel(model.type)}</p>
        </div>
        {model.contextSize && (
          <div className="space-y-1">
            <p className="text-muted-foreground">{t('common.model.selector.labels.contextWindow')}</p>
            <p>
              {model.contextSize.toLocaleString(i18n.language)} {t('common.model.selector.tokens')}
            </p>
          </div>
        )}
      </div>

      {model.capabilities && model.capabilities.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">{t('common.model.selector.labels.capabilities')}</p>
          <div className="flex flex-wrap gap-1">
            {model.capabilities.map((capability) => (
              <Badge key={capability} variant="secondary" className="text-xs">
                {getCapabilityLabel(capability)}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {model.tags && model.tags.length > 0 && (
        <div className="flex gap-1 mt-2">
          {model.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="text-xs">
              {getTagLabel(tag)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}

export { SelectModel }
