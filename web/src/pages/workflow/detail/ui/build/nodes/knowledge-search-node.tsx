import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Search, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const KnowledgeSearchNodeInfo = {
  type: 'knowledge-search-node',
  labelKey: 'workflow.detail.nodes.knowledgeSearch.label',
  descriptionKey: 'workflow.detail.nodes.knowledgeSearch.description',
  label: 'Knowledge Search',
  category: 'knowledge',
  description: 'Search relevant information from knowledge bases',
  color: 'indigo-500',
  icon: 'Search',
}

export const KnowledgeSearchNodeDefaultData = {
  label: 'Knowledge Search',
  dataSource: 'knowledge_base',
  topK: 3,
  similarityThreshold: 0.7,
  rerank: false,
  filters: [],
}

// Knowledge search node component.
const KnowledgeSearchNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-indigo-500' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Search className="h-4 w-4 text-indigo-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.knowledgeSearch.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.dataSource
          ? t('workflow.detail.nodes.knowledgeSearch.previewSource', {
            value: t(`workflow.detail.nodes.knowledgeSearch.dataSources.${data.dataSource}`),
          })
          : t('workflow.detail.nodes.knowledgeSearch.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-indigo-500 border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-indigo-500 border-2 border-background"
      />
    </div>
  )
}

export const KnowledgeSearchNode = memo(KnowledgeSearchNodeComponent)

interface KnowledgeSearchPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const KnowledgeSearchProperties: React.FC<KnowledgeSearchPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  const addFilter = () => {
    const filters = [...(data.filters || []), { field: '', operator: 'equals', value: '' }]
    handleChange('filters', filters)
  }

  const removeFilter = (index: number) => {
    const filters = [...(data.filters || [])]
    filters.splice(index, 1)
    handleChange('filters', filters)
  }

  const updateFilter = (index: number, field: string, value: string) => {
    const filters = [...(data.filters || [])]
    filters[index] = { ...filters[index], [field]: value }
    handleChange('filters', filters)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.detail.nodes.common.nameLabel')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.detail.nodes.knowledgeSearch.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="dataSource">{t('workflow.detail.nodes.knowledgeSearch.fields.dataSourceLabel')}</Label>
        <Select
          value={data.dataSource || ''}
          onValueChange={(value) => handleChange('dataSource', value)}
        >
          <SelectTrigger id="dataSource">
            <SelectValue placeholder={t('workflow.detail.nodes.knowledgeSearch.placeholders.dataSource')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="knowledge_base">{t('workflow.detail.nodes.knowledgeSearch.dataSources.knowledge_base')}</SelectItem>
            <SelectItem value="document_store">{t('workflow.detail.nodes.knowledgeSearch.dataSources.document_store')}</SelectItem>
            <SelectItem value="vector_db">{t('workflow.detail.nodes.knowledgeSearch.dataSources.vector_db')}</SelectItem>
            <SelectItem value="custom">{t('workflow.detail.nodes.knowledgeSearch.dataSources.custom')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {data.dataSource === 'custom' && (
        <div className="space-y-2">
          <Label htmlFor="customSource">{t('workflow.detail.nodes.knowledgeSearch.fields.customSourceLabel')}</Label>
          <Input
            id="customSource"
            value={data.customSource || ''}
            onChange={(e) => handleChange('customSource', e.target.value)}
            placeholder={t('workflow.detail.nodes.knowledgeSearch.placeholders.customSource')}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="query">{t('workflow.detail.nodes.knowledgeSearch.fields.queryLabel')}</Label>
        <Textarea
          id="query"
          value={data.query || ''}
          onChange={(e) => handleChange('query', e.target.value)}
          placeholder={t('workflow.detail.nodes.knowledgeSearch.placeholders.query')}
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="topK">{t('workflow.detail.nodes.knowledgeSearch.fields.topKLabel', { value: data.topK || 3 })}</Label>
        </div>
        <Slider
          id="topK"
          min={1}
          max={20}
          step={1}
          value={[data.topK || 3]}
          onValueChange={(value) => handleChange('topK', value[0])}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="similarityThreshold">{t('workflow.detail.nodes.knowledgeSearch.fields.similarityLabel', { value: data.similarityThreshold || 0.7 })}</Label>
        </div>
        <Slider
          id="similarityThreshold"
          min={0}
          max={1}
          step={0.05}
          value={[data.similarityThreshold || 0.7]}
          onValueChange={(value) => handleChange('similarityThreshold', value[0])}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('workflow.detail.nodes.knowledgeSearch.fields.filtersLabel')}</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addFilter}
            className="h-8 px-2"
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('workflow.detail.nodes.knowledgeSearch.actions.addFilter')}
          </Button>
        </div>

        <div className="space-y-3 mt-2">
          {(data.filters || []).map((filter: any, index: number) => (
            <div key={index} className="flex items-start gap-2 p-2 border rounded-md bg-muted/20">
              <div className="flex-1 space-y-2">
                <div className="flex gap-2">
                  <Input
                    value={filter.field}
                    onChange={(e) => updateFilter(index, 'field', e.target.value)}
                    placeholder={t('workflow.detail.nodes.knowledgeSearch.placeholders.filterField')}
                    className="h-8 flex-1"
                  />
                  <Select
                    value={filter.operator}
                    onValueChange={(value) => updateFilter(index, 'operator', value)}
                  >
                    <SelectTrigger className="h-8 w-28">
                      <SelectValue placeholder={t('workflow.detail.nodes.knowledgeSearch.placeholders.filterOperator')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="equals">{t('workflow.detail.nodes.knowledgeSearch.operators.equals')}</SelectItem>
                      <SelectItem value="contains">{t('workflow.detail.nodes.knowledgeSearch.operators.contains')}</SelectItem>
                      <SelectItem value="startsWith">{t('workflow.detail.nodes.knowledgeSearch.operators.startsWith')}</SelectItem>
                      <SelectItem value="endsWith">{t('workflow.detail.nodes.knowledgeSearch.operators.endsWith')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Input
                  value={filter.value}
                  onChange={(e) => updateFilter(index, 'value', e.target.value)}
                  placeholder={t('workflow.detail.nodes.knowledgeSearch.placeholders.filterValue')}
                  className="h-8"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeFilter(index)}
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
          id="rerank"
          checked={data.rerank || false}
          onCheckedChange={(checked) => handleChange('rerank', checked)}
        />
        <Label htmlFor="rerank">{t('workflow.detail.nodes.knowledgeSearch.fields.rerankLabel')}</Label>
      </div>
    </div>
  )
}
