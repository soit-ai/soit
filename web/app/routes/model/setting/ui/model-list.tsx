import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Plus } from 'lucide-react';
import { ModelItem } from './model-item';
import { ModelForm } from './model-form';
import type { ModelConfig, ModelListProps } from './types';
import { useDrawer } from '@/hooks/use-drawer';
import { DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer';
import {
  listProviderModels,
  updateProviderModel,
  createProviderModel,
  deleteProviderModel,
} from '@/services/provider-service';
import { useToast } from '@/hooks/use-toast';
import { useTranslation } from '@/i18n';

export function ModelList({ onSaveModel, onDeleteModel, provider, title }: ModelListProps) {
  const { t } = useTranslation();
  const drawer = useDrawer();
  const { toast } = useToast();
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const resolvedTitle = title ?? t('model.list.title');

  // Load models
  useEffect(() => {
    if (provider) {
      loadModels();
    }
  }, [provider]);

  const loadModels = async () => {
    try {
      setLoading(true);
      const data = await listProviderModels(provider);
      setModels(data);
    } catch (error) {
      console.error('Failed to load models:', error);
      toast({
        title: t('model.list.loadFailedTitle'),
        description: t('model.list.loadFailedDescription'),
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveModel = async (model: ModelConfig) => {
    try {
      let updatedModel: ModelConfig;
      if (model.id) {
        updatedModel = await updateProviderModel(provider, model.id, model);
      } else {
        updatedModel = await createProviderModel(provider, model);
      }

      // Update local state
      if (model.id) {
        const updatedModels = models.map(m =>
          m.id === model.id ? updatedModel : m
        );
        setModels(updatedModels);
      } else {
        setModels([...models, updatedModel]);
      }

      onSaveModel(updatedModel);
      drawer.close();

      toast({
        title: t('model.list.saveSuccessTitle'),
        description: t('model.list.saveSuccessDescription'),
      });
    } catch (error) {
      console.error('Failed to save model:', error);
      toast({
        title: t('model.list.saveFailedTitle'),
        description: t('model.list.saveFailedDescription'),
        type: 'error',
      });
    }
  };

  const handleDeleteModel = async (id: string) => {
    if (confirm(t('model.list.deleteConfirm'))) {
      try {
        await deleteProviderModel(provider, id);
        setModels(models.filter(m => m.id !== id));
        onDeleteModel(id);

        toast({
          title: t('model.list.deleteSuccessTitle'),
          description: t('model.list.deleteSuccessDescription'),
        });
      } catch (error) {
        console.error('Failed to delete model:', error);
        toast({
          title: t('model.list.deleteFailedTitle'),
          description: t('model.list.deleteFailedDescription'),
          type: 'error',
        });
      }
    }
  };

  const handleToggleActive = async (id: string, isActive: boolean) => {
    try {
      const model = models.find(m => m.id === id);
      if (!model) return;

      const updatedModel = await updateProviderModel(provider, id, { enabled: isActive });
      const updatedModels = models.map(m =>
        m.id === id ? updatedModel : m
      );
      setModels(updatedModels);

      onSaveModel(updatedModel);

      toast({
        title: t('model.list.toggleSuccessTitle'),
        description: t('model.list.toggleSuccessDescription', { status: isActive ? t('model.list.status.enabled') : t('model.list.status.disabled') }),
      });
    } catch (error) {
      console.error('Failed to toggle model status:', error);
      toast({
        title: t('model.list.toggleFailedTitle'),
        description: t('model.list.toggleFailedDescription'),
        type: 'error',
      });
    }
  };

  const handleEditModel = (model: ModelConfig) => {
    openModelFormDrawer(model, t('model.list.editTitle'));
  };

  const handleAddModel = () => {
      const newModel: ModelConfig = {
      id: '',
      providerId: provider,
      providerKind: '',
      modelId: '',
      displayName: '',
      description: '',
      capabilities: [],
      capabilitiesJson: {},
      status: 'active',
      enabled: true,
      source: 'local',
      architecture: {
        modality: 'text->text',
        input_modalities: ['text'],
        output_modalities: ['text'],
        tokenizer: 'GPT',
      },
      capabilityMatrix: {},
      parameterConfig: {
        supported_parameters: ['temperature', 'top_p', 'max_tokens'],
        default_parameters: {
          temperature: 0.7,
          top_p: 1,
          max_tokens: 4096,
        },
      },
      pricing: {
        currency: 'USD',
        pricing_source: 'manual',
        prompt: { amount: 0, unit: '1M_tokens' },
        completion: { amount: 0, unit: '1M_tokens' },
        request: { amount: 0, unit: 'request' },
      },
      diagnostics: {
        last_test_status: 'skipped',
        test_mode: 'chat',
        test_prompt: 'Please reply with one sentence: diagnostics passed.',
        timeout_ms: 30000,
        support: { catalog: 'unknown', diagnostics: 'unknown', runtime: 'unknown' },
        runtime_stats: { month_calls: 0, month_tokens: 0, avg_latency_ms: 0, error_rate: 0 },
      },
      rawMeta: {},
      userOverridesJson: {},
      syncStatus: 'never_synced',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    openModelFormDrawer(newModel, t('model.list.addTitle'));
  };

  const openModelFormDrawer = (model: ModelConfig, title: string) => {
    const ModelFormContent = () => {
      const [currentModel, setCurrentModel] = useState<ModelConfig>(model);

      const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        handleSaveModel(currentModel);
      };

      return (
        <ModelForm
          model={currentModel}
          onSave={handleFormSubmit}
          onCancel={() => drawer.close()}
          onChange={(updatedModel) => setCurrentModel(updatedModel)}
          title={title}
        />
      );
    };

    drawer.open(<ModelFormContent />, {
      direction: 'right',
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-hidden h-full">
        <DrawerHeader>
          <DrawerTitle className="text-sm font-bold">{resolvedTitle}</DrawerTitle>
          <DrawerDescription>
            {t('model.list.description')}
          </DrawerDescription>
        </DrawerHeader>
        <ScrollArea className="flex-1 h-full p-4">
          <div className="space-y-4 p-1">
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('model.list.loading')}
              </div>
            ) : models.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('model.list.empty')}
              </div>
            ) : (
              models.map((model) => (
                <ModelItem
                  key={model.id}
                  model={model}
                  onEdit={handleEditModel}
                  onDelete={handleDeleteModel}
                  onToggleActive={handleToggleActive}
                />
              ))
            )}
          </div>
        </ScrollArea>
      </div>
      <DrawerFooter className="border-t">
        <Button
          className="w-full"
          onClick={handleAddModel}
        >
          <Plus className="w-4 h-4 mr-2" />
          {t('model.list.addTitle')}
        </Button>
      </DrawerFooter>
    </div>
  );
}
