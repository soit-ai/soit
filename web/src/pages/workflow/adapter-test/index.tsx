import React, { useState, useEffect } from 'react';
import { Card, Tabs, Select, Form, Input, Button, Alert, Spin, Typography, Divider } from 'antd';
import { ApiOutlined, FunctionOutlined, CodeOutlined, ExperimentOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { CodeBlock } from '@/components/ui/code-block';
import { useRequest } from 'ahooks';
import { listWorkflows, executeWorkflow } from '@/services/workflow';
import { useTranslation } from '@/i18n';

const { TabPane } = Tabs;
const { Option } = Select;
const { TextArea } = Input;
const { Title, Text } = Typography;

interface WorkflowOption {
  id: string;
  name: string;
}

const AdapterTestPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('http');
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>('');
  const [workflowName, setWorkflowName] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [form] = Form.useForm();
  const { t } = useTranslation();

  // Fetch workflow list.
  const { data: workflowList, loading: loadingWorkflows } = useRequest(
    () => listWorkflows({ page_size: 100 }),
    {
      onSuccess: (data) => {
        if (data?.items && data.items.length > 0) {
          setSelectedWorkflow(data.items[0].id);
          setWorkflowName(data.items[0].name);
          form.setFieldsValue({
            workflow_id: data.items[0].id
          });
        }
      }
    }
  );

  // Handle workflow selection changes.
  const handleWorkflowChange = (value: string) => {
    setSelectedWorkflow(value);
    const workflow = workflowList?.items?.find(w => w.id === value);
    if (workflow) {
      setWorkflowName(workflow.name);
    }
  };

  // Handle adapter type changes.
  const handleAdapterTypeChange = (value: string) => {
    setActiveTab(value);
  };

  // Handle form submission.
  const handleSubmit = async (values: any) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // Parse inputs and options.
      const inputs = JSON.parse(values.inputs || '{}');
      const options = values.options ? JSON.parse(values.options) : {};
      
      const data = await executeWorkflow(values.workflow_id, inputs);
      setResult(data);
    } catch (err: any) {
      setError(err.message || t('workflow.adapterTest.errorMessage'));
    } finally {
      setLoading(false);
    }
  };

  const getAdapterDisplayName = () => {
    switch (activeTab) {
      case 'http':
        return t('workflow.adapterTest.tabs.http');
      case 'function':
        return t('workflow.adapterTest.tabs.function');
      case 'mcp':
        return t('workflow.adapterTest.tabs.mcp');
      default:
        return activeTab;
    }
  };

  return (
    <PageContainer
      header={{
        title: t('workflow.adapterTest.title'),
        subTitle: t('workflow.adapterTest.subtitle'),
      }}
    >
      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            inputs: JSON.stringify({
              "param1": t('workflow.adapterTest.sample.param1'),
              "param2": t('workflow.adapterTest.sample.param2')
            }, null, 2),
            options: JSON.stringify({
              "timeout": 30,
              "cache": false
            }, null, 2)
          }}
        >
          <Form.Item
            name="workflow_id"
            label={t('workflow.adapterTest.form.workflowLabel')}
            rules={[{ required: true, message: t('workflow.adapterTest.form.workflowRequired') }]}
          >
            <Select 
              loading={loadingWorkflows}
              onChange={handleWorkflowChange}
              placeholder={t('workflow.adapterTest.form.workflowPlaceholder')}
            >
              {workflowList?.items?.map((workflow: WorkflowOption) => (
                <Option key={workflow.id} value={workflow.id}>
                  {workflow.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item
            label={t('workflow.adapterTest.form.adapterLabel')}
          >
            <Tabs 
              activeKey={activeTab} 
              onChange={handleAdapterTypeChange}
              type="card"
            >
              <TabPane 
                tab={<span><ApiOutlined /> {t('workflow.adapterTest.tabs.http')}</span>} 
                key="http"
              />
              <TabPane 
                tab={<span><FunctionOutlined /> {t('workflow.adapterTest.tabs.function')}</span>} 
                key="function"
              />
              <TabPane 
                tab={<span><CodeOutlined /> {t('workflow.adapterTest.tabs.mcp')}</span>} 
                key="mcp"
              />
            </Tabs>
          </Form.Item>
          
          <Form.Item
            name="inputs"
            label={t('workflow.adapterTest.form.inputsLabel')}
            rules={[
              { required: true, message: t('workflow.adapterTest.form.inputsRequired') },
              {
                validator: (_, value) => {
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch (error) {
                    return Promise.reject(t('workflow.adapterTest.form.inputsInvalid'));
                  }
                }
              }
            ]}
          >
            <TextArea
              rows={6}
              placeholder={t('workflow.adapterTest.form.inputsPlaceholder')}
              className="font-mono text-sm"
            />
          </Form.Item>
          
          <Form.Item
            name="options"
            label={t('workflow.adapterTest.form.optionsLabel')}
            rules={[
              {
                validator: (_, value) => {
                  if (!value) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch (error) {
                    return Promise.reject(t('workflow.adapterTest.form.optionsInvalid'));
                  }
                }
              }
            ]}
          >
            <TextArea
              rows={4}
              placeholder={t('workflow.adapterTest.form.optionsPlaceholder')}
              className="font-mono text-sm"
            />
          </Form.Item>
          
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              icon={<ExperimentOutlined />}
              loading={loading}
            >
              {t('workflow.adapterTest.form.submit', { adapter: getAdapterDisplayName() })}
            </Button>
          </Form.Item>
        </Form>
        
        {loading && (
          <div className="py-4 flex justify-center">
            <Spin tip={t('workflow.adapterTest.loading')} />
          </div>
        )}
        
        {error && (
          <Alert
            message={t('workflow.adapterTest.errorTitle')}
            description={error}
            type="error"
            showIcon
            className="mb-4"
          />
        )}
        
        {result && (
          <div className="mt-4">
            <Divider orientation="left">{t('workflow.adapterTest.resultTitle')}</Divider>
            <CodeBlock
              language="json"
              value={JSON.stringify(result, null, 2)}
              showLineNumbers={true}
              showCopyButton={true}
            />
          </div>
        )}
      </Card>
    </PageContainer>
  );
};

export default AdapterTestPage;
