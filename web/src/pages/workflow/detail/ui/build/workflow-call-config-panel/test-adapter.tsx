import React, { useState } from 'react';
import { Card, Form, Input, Button, Typography, Alert, Spin } from 'antd';
import { SendOutlined, ReloadOutlined } from '@ant-design/icons';
import { CodeBlock } from '@/components/ui/code-block';
import { useTranslation } from '@/i18n';

const { Title } = Typography;
const { TextArea } = Input;

interface TestAdapterProps {
  workflowId: string;
  adapterType: string;
}

const TestAdapter: React.FC<TestAdapterProps> = ({ workflowId, adapterType }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Resolve adapter display name.
  const getAdapterDisplayName = () => {
    switch (adapterType) {
      case 'http':
        return 'HTTP API';
      case 'function':
        return t('workflow.detail.callConfig.testAdapter.adapterTypes.function');
      case 'mcp':
        return t('workflow.detail.callConfig.testAdapter.adapterTypes.mcp');
      default:
        return adapterType;
    }
  };

  // Provide default input payload.
  const getDefaultInputs = () => {
    return JSON.stringify({
      param1: t('workflow.detail.callConfig.testAdapter.defaults.input1'),
      param2: t('workflow.detail.callConfig.testAdapter.defaults.input2'),
    }, null, 2);
  };

  // Provide default options payload.
  const getDefaultOptions = () => {
    return JSON.stringify({
      timeout: 30,
      cache: false,
    }, null, 2);
  };

  // Handle test execution.
  const handleTest = async (values: any) => {
    setLoading(true);
    setError(null);

    try {
      // Parse inputs and options.
      const inputs = JSON.parse(values.inputs);
      const options = JSON.parse(values.options);

      // Execute adapter call based on type.
      if (adapterType === 'http') {
        // Build HTTP request.
        const response = await fetch(`/api/workflow/execute/${workflowId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            inputs,
            options,
          }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || t('workflow.detail.callConfig.testAdapter.errors.callFailed'));
        }

        setResult(data);
      } else {
        // For other adapter types, use a simulated HTTP endpoint.
        const response = await fetch('/api/workflow/test-adapter', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            adapter_type: adapterType,
            workflow_id: workflowId,
            inputs,
            options,
          }),
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || t('workflow.detail.callConfig.testAdapter.errors.callFailed'));
        }

        setResult(data);
      }
    } catch (err: any) {
      setError(err.message || t('workflow.detail.callConfig.testAdapter.errors.callFailed'));
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Reset form and output.
  const handleReset = () => {
    form.resetFields();
    setResult(null);
    setError(null);
  };

  return (
    <Card className="test-adapter-card" bordered={false}>
      <Title level={5}>
        {t('workflow.detail.callConfig.testAdapter.title', { name: getAdapterDisplayName() })}
      </Title>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleTest}
        initialValues={{
          inputs: getDefaultInputs(),
          options: getDefaultOptions(),
        }}
      >
        <Form.Item
          name="inputs"
          label={t('workflow.detail.callConfig.testAdapter.fields.inputs')}
          rules={[
            { required: true, message: t('workflow.detail.callConfig.testAdapter.validation.inputsRequired') },
            {
              validator: (_, value) => {
                try {
                  JSON.parse(value);
                  return Promise.resolve();
                } catch (error) {
                  return Promise.reject(t('workflow.detail.callConfig.testAdapter.validation.inputsInvalid'));
                }
              },
            },
          ]}
        >
          <TextArea
            rows={6}
            placeholder={t('workflow.detail.callConfig.testAdapter.placeholders.inputs')}
            className="font-mono text-sm"
          />
        </Form.Item>

        <Form.Item
          name="options"
          label={t('workflow.detail.callConfig.testAdapter.fields.options')}
          rules={[
            {
              validator: (_, value) => {
                if (!value) return Promise.resolve();
                try {
                  JSON.parse(value);
                  return Promise.resolve();
                } catch (error) {
                  return Promise.reject(t('workflow.detail.callConfig.testAdapter.validation.optionsInvalid'));
                }
              },
            },
          ]}
        >
          <TextArea
            rows={4}
            placeholder={t('workflow.detail.callConfig.testAdapter.placeholders.options')}
            className="font-mono text-sm"
          />
        </Form.Item>

        <Form.Item>
          <div className="flex gap-2">
            <Button
              type="primary"
              htmlType="submit"
              icon={<SendOutlined />}
              loading={loading}
            >
              {t('workflow.detail.callConfig.testAdapter.actions.test')}
            </Button>
            <Button
              onClick={handleReset}
              icon={<ReloadOutlined />}
            >
              {t('workflow.detail.callConfig.testAdapter.actions.reset')}
            </Button>
          </div>
        </Form.Item>
      </Form>

      {loading && (
        <div className="py-4 flex justify-center">
          <Spin tip={t('workflow.detail.callConfig.testAdapter.status.loading')} />
        </div>
      )}

      {error && (
        <Alert
          message={t('workflow.detail.callConfig.testAdapter.errors.callFailed')}
          description={error}
          type="error"
          showIcon
          className="mb-4"
        />
      )}

      {result && (
        <div className="mt-4">
          <Title level={5}>{t('workflow.detail.callConfig.testAdapter.resultTitle')}</Title>
          <CodeBlock
            language="json"
            value={JSON.stringify(result, null, 2)}
            className="mt-2"
          />
        </div>
      )}
    </Card>
  );
};

export default TestAdapter;
