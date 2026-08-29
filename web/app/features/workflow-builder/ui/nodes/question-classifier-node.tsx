import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { FilterX, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const QuestionClassifierNodeInfo = {
  type: 'question-classifier-node',
  labelKey: 'workflow.detail.nodes.questionClassifier.label',
  descriptionKey: 'workflow.detail.nodes.questionClassifier.description',
  label: 'Question Classifier',
  category: 'tool',
  description: 'Classify and route questions',
  color: 'cat-amber',
  icon: 'FilterX',
}

export const QuestionClassifierNodeDefaultData = {
  label: 'Question Classifier',
  classifierType: 'llm',
  model: 'gpt-3.5-turbo',
  prompt: '',
  categories: [],
  fallback: true,
  fallbackMessage: 'Unclassified question',
}

// Question classifier node component.
const QuestionClassifierNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-amber' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <FilterX className="h-4 w-4 text-cat-amber" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.questionClassifier.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.detail.nodes.questionClassifier.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-amber border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-amber border-2 border-background"
      />
    </div>
  )
}

export const QuestionClassifierNode = memo(QuestionClassifierNodeComponent)

interface QuestionClassifierPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const QuestionClassifierProperties: React.FC<QuestionClassifierPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  const addCategory = () => {
    const categories = [...(data.categories || []), { name: '', description: '', examples: '' }]
    handleChange('categories', categories)
  }

  const removeCategory = (index: number) => {
    const categories = [...(data.categories || [])]
    categories.splice(index, 1)
    handleChange('categories', categories)
  }

  const updateCategory = (index: number, field: string, value: string) => {
    const categories = [...(data.categories || [])]
    categories[index] = { ...categories[index], [field]: value }
    handleChange('categories', categories)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.detail.nodes.common.nameLabel')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.detail.nodes.questionClassifier.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="classifierType">{t('workflow.detail.nodes.questionClassifier.fields.classifierTypeLabel')}</Label>
        <Select
          value={data.classifierType || 'llm'}
          onValueChange={(value) => value != null && handleChange('classifierType', value)}
        >
          <SelectTrigger id="classifierType">
            <SelectValue placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.classifierType')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="llm">{t('workflow.detail.nodes.questionClassifier.types.llm')}</SelectItem>
            <SelectItem value="rule">{t('workflow.detail.nodes.questionClassifier.types.rule')}</SelectItem>
            <SelectItem value="embedding">{t('workflow.detail.nodes.questionClassifier.types.embedding')}</SelectItem>
            <SelectItem value="hybrid">{t('workflow.detail.nodes.questionClassifier.types.hybrid')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="model">{t('workflow.detail.nodes.common.modelLabel')}</Label>
        <Select
          value={data.model || 'gpt-3.5-turbo'}
          onValueChange={(value) => value != null && handleChange('model', value)}
        >
          <SelectTrigger id="model">
            <SelectValue placeholder={t('workflow.detail.nodes.common.modelPlaceholder')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
            <SelectItem value="gpt-4">GPT-4</SelectItem>
            <SelectItem value="custom">{t('workflow.detail.nodes.questionClassifier.types.customModel')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {data.model === 'custom' && (
        <div className="space-y-2">
          <Label htmlFor="customModel">{t('workflow.detail.nodes.questionClassifier.fields.customModelLabel')}</Label>
          <Input
            id="customModel"
            value={data.customModel || ''}
            onChange={(e) => handleChange('customModel', e.target.value)}
            placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.customModel')}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="prompt">{t('workflow.detail.nodes.questionClassifier.fields.promptLabel')}</Label>
        <Textarea
          id="prompt"
          value={data.prompt || ''}
          onChange={(e) => handleChange('prompt', e.target.value)}
          placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.prompt')}
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('workflow.detail.nodes.questionClassifier.fields.categoriesLabel')}</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addCategory}
            className="h-8 px-2"
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('workflow.detail.nodes.questionClassifier.actions.addCategory')}
          </Button>
        </div>

        <div className="space-y-3 mt-2">
          {(data.categories || []).map((category: any, index: number) => (
            <div key={index} className="flex items-start gap-2 p-2 border rounded-md bg-muted/20">
              <div className="flex-1 space-y-2">
                <Input
                  value={category.name}
                  onChange={(e) => updateCategory(index, 'name', e.target.value)}
                  placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.categoryName')}
                  className="h-8"
                />
                <Textarea
                  value={category.description}
                  onChange={(e) => updateCategory(index, 'description', e.target.value)}
                  placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.categoryDescription')}
                  className="min-h-[60px] text-xs"
                />
                <Textarea
                  value={category.examples}
                  onChange={(e) => updateCategory(index, 'examples', e.target.value)}
                  placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.categoryExamples')}
                  className="min-h-[60px] text-xs"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeCategory(index)}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="fallback"
          checked={data.fallback ?? true}
          onCheckedChange={(checked) => handleChange('fallback', checked)}
        />
        <Label htmlFor="fallback">{t('workflow.detail.nodes.questionClassifier.fields.fallbackLabel')}</Label>
      </div>

      <div className="space-y-2">
        <Label htmlFor="defaultCategory">{t('workflow.detail.nodes.questionClassifier.fields.defaultCategoryLabel')}</Label>
        <Input
          id="defaultCategory"
          value={data.defaultCategory || t('workflow.detail.nodes.questionClassifier.defaults.defaultCategory')}
          onChange={(e) => handleChange('defaultCategory', e.target.value)}
          placeholder={t('workflow.detail.nodes.questionClassifier.placeholders.defaultCategory')}
          disabled={!data.fallback}
        />
      </div>
    </div>
  )
}
