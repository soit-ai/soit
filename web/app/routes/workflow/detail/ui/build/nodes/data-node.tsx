import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Database } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'
import type { TranslationKey } from '@/i18n/types'

export const DataNodeInfo = {
  type: 'data-node',
  labelKey: 'workflow.detail.nodes.data.label',
  descriptionKey: 'workflow.detail.nodes.data.description',
  label: 'Data Source',
  category: 'data',
  description: 'Connect external data sources',
  color: 'cat-cyan',
  icon: 'Database',
}

export const DataNodeDefaultData = {
  label: 'Data Source',
  dataType: 'document',
  source: '',
  cache: false,
}

// Data source node component.
const DataNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-primary' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Database className="h-4 w-4 text-cat-cyan" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.data.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-1">
        {t('workflow.detail.nodes.data.fields.typeLabel')}: {t(`workflow.detail.nodes.data.dataTypes.${data.dataType || 'document'}` as TranslationKey)}
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.source
          ? t('workflow.detail.nodes.data.previewSource', { value: data.source })
          : t('workflow.detail.nodes.data.previewSourceEmpty')}
      </div>

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-cyan border-2 border-background"
      />
    </div>
  )
}

export const DataNode = memo(DataNodeComponent)

interface DataPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const DataProperties: React.FC<DataPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.detail.nodes.common.nameLabel')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.detail.nodes.data.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="dataType">{t('workflow.detail.nodes.data.fields.dataTypeLabel')}</Label>
        <Select
          value={data.dataType || 'document'}
          onValueChange={(value) => handleChange('dataType', value)}
        >
          <SelectTrigger id="dataType">
            <SelectValue placeholder={t('workflow.detail.nodes.data.placeholders.dataType')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="document">{t('workflow.detail.nodes.data.dataTypes.document')}</SelectItem>
            <SelectItem value="database">{t('workflow.detail.nodes.data.dataTypes.database')}</SelectItem>
            <SelectItem value="api">{t('workflow.detail.nodes.data.dataTypes.api')}</SelectItem>
            <SelectItem value="vector">{t('workflow.detail.nodes.data.dataTypes.vector')}</SelectItem>
            <SelectItem value="file">{t('workflow.detail.nodes.data.dataTypes.file')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="source">{t('workflow.detail.nodes.data.fields.sourceLabel')}</Label>
        <Input
          id="source"
          value={data.source || ''}
          onChange={(e) => handleChange('source', e.target.value)}
          placeholder={t('workflow.detail.nodes.data.placeholders.source')}
        />
      </div>

      {data.dataType === 'document' && (
        <div className="space-y-2">
          <Label htmlFor="documentId">{t('workflow.detail.nodes.data.fields.documentIdLabel')}</Label>
          <Input
            id="documentId"
            value={data.documentId || ''}
            onChange={(e) => handleChange('documentId', e.target.value)}
            placeholder={t('workflow.detail.nodes.data.placeholders.documentId')}
          />
        </div>
      )}

      {data.dataType === 'database' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="connectionString">{t('workflow.detail.nodes.data.fields.connectionStringLabel')}</Label>
            <Input
              id="connectionString"
              value={data.connectionString || ''}
              onChange={(e) => handleChange('connectionString', e.target.value)}
              placeholder={t('workflow.detail.nodes.data.placeholders.connectionString')}
              type="password"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="query">{t('workflow.detail.nodes.data.fields.queryLabel')}</Label>
            <Input
              id="query"
              value={data.query || ''}
              onChange={(e) => handleChange('query', e.target.value)}
              placeholder={t('workflow.detail.nodes.data.placeholders.query')}
            />
          </div>
        </>
      )}

      {data.dataType === 'api' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="endpoint">{t('workflow.detail.nodes.data.fields.endpointLabel')}</Label>
            <Input
              id="endpoint"
              value={data.endpoint || ''}
              onChange={(e) => handleChange('endpoint', e.target.value)}
              placeholder={t('workflow.detail.nodes.data.placeholders.endpoint')}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="method">{t('workflow.detail.nodes.data.fields.methodLabel')}</Label>
            <Select
              value={data.method || 'GET'}
              onValueChange={(value) => handleChange('method', value)}
            >
              <SelectTrigger id="method">
                <SelectValue placeholder={t('workflow.detail.nodes.data.placeholders.method')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="GET">GET</SelectItem>
                <SelectItem value="POST">POST</SelectItem>
                <SelectItem value="PUT">PUT</SelectItem>
                <SelectItem value="DELETE">DELETE</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </>
      )}

      <div className="flex items-center space-x-2">
        <Switch
          id="cache"
          checked={data.cache || false}
          onCheckedChange={(checked) => handleChange('cache', checked)}
        />
        <Label htmlFor="cache">{t('workflow.detail.nodes.data.fields.cacheLabel')}</Label>
      </div>
    </div>
  )
}
