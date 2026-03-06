import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Pencil, Trash2 } from 'lucide-react';
import type { ModelConfig, ModelItemProps } from './types';
import { useTranslation } from '@/i18n';

export function ModelItem({ model, onEdit, onDelete, onToggleActive }: ModelItemProps) {
  const { t } = useTranslation();

  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <h3 className="font-medium">{model.displayName || model.modelId}</h3>
            <Badge variant="secondary">{model.source}</Badge>
            <Badge variant={model.syncStatus === 'in_sync' ? 'default' : 'secondary'}>
              {model.syncStatus}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{model.modelId}</p>
        </div>
        <div className="flex items-end space-x-2 flex-col justify-center">
          <Switch
            checked={model.enabled}
            onCheckedChange={(checked) => onToggleActive && onToggleActive(model.id, checked)}
            aria-label={model.enabled ? t('system.model.list.disableAria') : t('system.model.list.enableAria')}
          />
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDelete(model.id)}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onEdit(model)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
