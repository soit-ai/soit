import React, { useState, useEffect } from 'react';
import { useClipboard } from 'use-clipboard-copy';
import { useTheme } from '@/components/theme-provider';
import { CodeOutlined, ApiOutlined, FunctionOutlined, CopyOutlined, ExperimentOutlined } from '@ant-design/icons';
import TestAdapter from './test-adapter';

// Import shadcn components
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { message } from 'antd';
import { API_BASE_URL } from '@/utils/request';
import { highlightCodeToHtml, plainCodeToHtml } from '@/lib/shiki';

// Add global styles.
const codeLineNumbersStyle = `
.shiki-with-line-numbers .line {
  position: relative;
  padding-left: 1rem;
  counter-increment: line;
}

.shiki-with-line-numbers .line::before {
  content: counter(line);
  position: absolute;
  left: -2rem;
  width: 1.5rem;
  text-align: right;
  color: var(--tw-prose-captions);
  opacity: 0.5;
  font-size: 0.75rem;
  user-select: none;
}
.shiki.github-dark {
  background-color: hsl(var(--muted-foreground) / 0.7) !important;
}
.shiki.github-light {
  background-color: hsl(var(--muted-foreground) / 0.7) !important;
}
.shiki {
  white-space: pre-wrap !important;
  word-wrap: break-word !important;
}
.shiki code {
  white-space: pre-wrap !important;
  word-break: break-all !important;
}
`

interface WorkflowCallConfigPanelProps {
  workflowId: string;
  workflowName: string;
  visible: boolean;
  onClose: () => void;
}

const WorkflowCallConfigPanel: React.FC<WorkflowCallConfigPanelProps> = ({
  workflowId,
  workflowName,
  visible,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState('http');
  const clipboard = useClipboard();
  const { theme } = useTheme();
  const [highlightedCode, setHighlightedCode] = useState<string>("");
  const executeEndpointPath = `${API_BASE_URL}/workflows/${workflowId}/execute`;
  const executeEndpointUrl = executeEndpointPath.startsWith('http')
    ? executeEndpointPath
    : `${window.location.origin}${executeEndpointPath}`;

  // Form schemas
  const httpFormSchema = z.object({
    authType: z.enum(["none", "token"]),
    includeHeaders: z.boolean(),
  });

  const functionFormSchema = z.object({
    importType: z.enum(["esm", "commonjs"]),
  });

  const mcpFormSchema = z.object({
    mcpVersion: z.string(),
  });

  // Initialize forms
  const httpForm = useForm<z.infer<typeof httpFormSchema>>({
    resolver: zodResolver(httpFormSchema),
    defaultValues: {
      authType: "none",
      includeHeaders: true,
    },
  });

  const functionForm = useForm<z.infer<typeof functionFormSchema>>({
    resolver: zodResolver(functionFormSchema),
    defaultValues: {
      importType: "esm",
    },
  });

  const mcpForm = useForm<z.infer<typeof mcpFormSchema>>({
    resolver: zodResolver(mcpFormSchema),
    defaultValues: {
      mcpVersion: "1.0",
    },
  });

  // Update code highlighting.
  useEffect(() => {
    let active = true;
    const loadHighlightedCode = async () => {
      const code = getCurrentSampleCode();
      try {
        const html = await highlightCodeToHtml({
          code,
          language: "javascript",
          showLineNumbers: true,
          theme: theme === "dark" ? "github-dark" : "github-light",
        });
        if (active) {
          setHighlightedCode(`<style>${codeLineNumbersStyle}</style>${html}`);
        }
      } catch (error) {
        console.error("Failed to highlight code:", error);
        if (active) {
          setHighlightedCode(plainCodeToHtml(code));
        }
      }
    };

    void loadHighlightedCode();
    return () => {
      active = false;
    };
  }, [activeTab, httpForm, functionForm, mcpForm, theme]);

  // HTTP sample code.
  const getHttpSampleCode = () => {
    const values = httpForm.watch();
    const { authType, includeHeaders } = values;
    
    let headers = '{}';
    if (includeHeaders) {
      headers = `{
  "Content-Type": "application/json"${authType === 'token' ? ',\n  "Authorization": "Bearer YOUR_API_TOKEN"' : ''}
}`;
    }
    
    return `// Call workflow using fetch API
const response = await fetch('${executeEndpointUrl}', {
  method: 'POST',
  headers: ${headers},
  body: JSON.stringify({
    // Add workflow input parameters here
    "param1": "value1",
    "param2": "value2"
  })
});

const result = await response.json();
console.info(result);`;
  };

  // Function call sample code.
  const getFunctionSampleCode = () => {
    const values = functionForm.watch();
    const { importType } = values;
    
    if (importType === 'esm') {
      return `// Import using ES modules
import { WorkflowService } from '@your-org/soit-sdk';

// Create workflow service instance
const workflowService = new WorkflowService();

// Execute workflow
const result = await workflowService.execute({
  workflow_id: '${workflowId}',
  inputs: {
    // Add workflow input parameters here
    "param1": "value1",
    "param2": "value2"
  },
  options: {
    // Optional execution options
    "timeout": 30,
    "cache": false
  }
});

console.info(result);`;
    } else {
      return `// Import using CommonJS
const { WorkflowService } = require('@your-org/soit-sdk');

// Create workflow service instance
const workflowService = new WorkflowService();

// Execute workflow
workflowService.execute({
  workflow_id: '${workflowId}',
  inputs: {
    // Add workflow input parameters here
    "param1": "value1",
    "param2": "value2"
  },
  options: {
    // Optional execution options
    "timeout": 30,
    "cache": false
  }
})
  .then(result => {
    console.info(result);
  })
  .catch(error => {
    console.error(error);
  });`;
    }
  };

  // MCP sample code.
  const getMcpSampleCode = () => {
    const values = mcpForm.watch();
    const { mcpVersion } = values;
    
    return `// Call workflow using MCP protocol
const mcpRequest = {
  version: "${mcpVersion || '1.0'}",
  id: "request-${Date.now()}",
  method: "workflow.execute",
  workflow_id: "${workflowId}",
  parameters: {
    // Add workflow input parameters here
    "param1": "value1",
    "param2": "value2"
  },
  options: {
    // Optional execution options
    "timeout": 30,
    "cache": false
  }
};

// Send MCP request
const response = await sendMcpRequest(mcpRequest);
console.info(response);`;
  };

  // Get sample code for active tab.
  const getCurrentSampleCode = () => {
    switch (activeTab) {
      case 'http':
        return getHttpSampleCode();
      case 'function':
        return getFunctionSampleCode();
      case 'mcp':
        return getMcpSampleCode();
      default:
        return '';
    }
  };

  // Copy sample code to clipboard.
  const handleCopyCode = () => {
    clipboard.copy(getCurrentSampleCode());
    message.success('Code copied to clipboard');
  };

  if (!visible) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <Card className="w-[80%] max-w-[900px] max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-lg font-semibold">Workflow Call Configuration - {workflowName}</h2>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
        
        <ScrollArea className="h-[calc(90vh-8rem)]">
          <div className="p-6">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="http">
                  <ApiOutlined className="mr-2" />
                  HTTP API
                </TabsTrigger>
                <TabsTrigger value="function">
                  <FunctionOutlined className="mr-2" />
                  Function Call
                </TabsTrigger>
                <TabsTrigger value="mcp">
                  <CodeOutlined className="mr-2" />
                  MCP Protocol
                </TabsTrigger>
              </TabsList>

              <TabsContent value="http">
                <Form {...httpForm}>
                  <form className="space-y-6">
                    <FormField
                      control={httpForm.control}
                      name="authType"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Authentication Type</FormLabel>
                          <Select onValueChange={field.onChange} defaultValue={field.value}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select authentication type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">No Authentication</SelectItem>
                              <SelectItem value="token">Token Authentication</SelectItem>
                            </SelectContent>
                          </Select>
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={httpForm.control}
                      name="includeHeaders"
                      render={({ field }) => (
                        <FormItem className="flex items-center justify-between rounded-lg border p-4">
                          <div className="space-y-0.5">
                            <FormLabel>Include Headers</FormLabel>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={field.onChange}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />

                    <Separator />
                    <div className="space-y-2">
                      <h3 className="text-sm font-medium">API Endpoint</h3>
                      <div className="flex items-center gap-2">
                        <code className="relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm">
                          {executeEndpointUrl}
                        </code>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            clipboard.copy(executeEndpointUrl);
                            message.success('Endpoint copied to clipboard');
                          }}
                        >
                          <CopyOutlined />
                        </Button>
                      </div>
                    </div>
                  </form>
                </Form>

                <Separator className="my-6" />

                <Tabs defaultValue="sample">
                  <TabsList>
                    <TabsTrigger value="sample">Sample Code</TabsTrigger>
                    <TabsTrigger value="test">
                      <ExperimentOutlined className="mr-2" />
                      Test Call
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="sample">
                    <div className="relative">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-2"
                        onClick={handleCopyCode}
                      >
                        <CopyOutlined />
                      </Button>
                      <div 
                        className="shiki-container w-full shiki-with-line-numbers text-sm"
                        dangerouslySetInnerHTML={{ __html: highlightedCode }} 
                        style={{
                          position: 'relative',
                          paddingLeft: '3rem',
                        }}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="test">
                    <TestAdapter workflowId={workflowId} adapterType="http" />
                  </TabsContent>
                </Tabs>
              </TabsContent>

              <TabsContent value="function">
                <Form {...functionForm}>
                  <form className="space-y-6">
                    <FormField
                      control={functionForm.control}
                      name="importType"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Import Type</FormLabel>
                          <Select onValueChange={field.onChange} defaultValue={field.value}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select import type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="esm">ES Modules (import)</SelectItem>
                              <SelectItem value="commonjs">CommonJS (require)</SelectItem>
                            </SelectContent>
                          </Select>
                        </FormItem>
                      )}
                    />

                    <Separator />
                    <div className="space-y-2">
                      <h3 className="text-sm font-medium">Workflow ID</h3>
                      <div className="flex items-center gap-2">
                        <code className="relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm">
                          {workflowId}
                        </code>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            clipboard.copy(workflowId);
                            message.success('Workflow ID copied to clipboard');
                          }}
                        >
                          <CopyOutlined />
                        </Button>
                      </div>
                    </div>
                  </form>
                </Form>

                <Separator className="my-6" />

                <Tabs defaultValue="sample">
                  <TabsList>
                    <TabsTrigger value="sample">Sample Code</TabsTrigger>
                    <TabsTrigger value="test">
                      <ExperimentOutlined className="mr-2" />
                      Test Call
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="sample">
                    <div className="relative">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-2"
                        onClick={handleCopyCode}
                      >
                        <CopyOutlined />
                      </Button>
                      <div 
                        className="shiki-container w-full shiki-with-line-numbers text-sm"
                        dangerouslySetInnerHTML={{ __html: highlightedCode }} 
                        style={{
                          position: 'relative',
                          paddingLeft: '3rem',
                        }}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="test">
                    <TestAdapter workflowId={workflowId} adapterType="function" />
                  </TabsContent>
                </Tabs>
              </TabsContent>

              <TabsContent value="mcp">
                <Form {...mcpForm}>
                  <form className="space-y-6">
                    <FormField
                      control={mcpForm.control}
                      name="mcpVersion"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>MCP Protocol Version</FormLabel>
                          <Select onValueChange={field.onChange} defaultValue={field.value}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select MCP protocol version" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="1.0">1.0</SelectItem>
                              <SelectItem value="1.1">1.1</SelectItem>
                            </SelectContent>
                          </Select>
                        </FormItem>
                      )}
                    />

                    <Separator />
                    <div className="space-y-2">
                      <h3 className="text-sm font-medium">Workflow ID</h3>
                      <div className="flex items-center gap-2">
                        <code className="relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm">
                          {workflowId}
                        </code>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            clipboard.copy(workflowId);
                            message.success('Workflow ID copied to clipboard');
                          }}
                        >
                          <CopyOutlined />
                        </Button>
                      </div>
                    </div>
                  </form>
                </Form>

                <Separator className="my-6" />

                <Tabs defaultValue="sample">
                  <TabsList>
                    <TabsTrigger value="sample">Sample Code</TabsTrigger>
                    <TabsTrigger value="test">
                      <ExperimentOutlined className="mr-2" />
                      Test Call
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="sample">
                    <div className="relative">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-2"
                        onClick={handleCopyCode}
                      >
                        <CopyOutlined />
                      </Button>
                      <div 
                        className="shiki-container w-full shiki-with-line-numbers text-sm"
                        dangerouslySetInnerHTML={{ __html: highlightedCode }} 
                        style={{
                          position: 'relative',
                          paddingLeft: '3rem',
                        }}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="test">
                    <TestAdapter workflowId={workflowId} adapterType="mcp" />
                  </TabsContent>
                </Tabs>
              </TabsContent>
            </Tabs>
          </div>
        </ScrollArea>
      </Card>
    </div>
  );
};

export default WorkflowCallConfigPanel;
