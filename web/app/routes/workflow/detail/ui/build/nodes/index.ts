import { TextNode, TextNodeInfo, TextNodeDefaultData, TextProperties } from './text-node'
import { PromptNode, PromptNodeInfo, PromptNodeDefaultData, PromptProperties } from './prompt-node'
import { LLMNode, LLMNodeInfo, LLMNodeDefaultData, LLMProperties } from './llm-node'
import { ToolNode, ToolNodeInfo, ToolNodeDefaultData, ToolProperties } from './tool-node'
import { DataNode, DataNodeInfo, DataNodeDefaultData, DataProperties } from './data-node'
import { OutputNode, OutputNodeInfo, OutputNodeDefaultData, OutputProperties } from './output-node'
import { KnowledgeSearchNode, KnowledgeSearchNodeInfo, KnowledgeSearchNodeDefaultData, KnowledgeSearchProperties } from './knowledge-search-node'
import { AgentNode, AgentNodeInfo, AgentNodeDefaultData, AgentProperties } from './agent-node'
import { QuestionClassifierNode, QuestionClassifierNodeInfo, QuestionClassifierNodeDefaultData, QuestionClassifierProperties } from './question-classifier-node'
import { LogicNode, LogicNodeInfo, LogicNodeDefaultData } from './logic-node'
import { ConditionalNode, ConditionalNodeInfo, ConditionalNodeDefaultData } from './conditional-node'
import { DeliveryNode, DeliveryNodeInfo, DeliveryNodeDefaultData } from './delivery-node'
import { LoopNode, LoopNodeInfo, LoopNodeDefaultData } from './loop-node'
import { TransformNode, TransformNodeInfo, TransformNodeDefaultData } from './transform-node'
import { CodeExecutionNode, CodeExecutionNodeInfo, CodeExecutionNodeDefaultData } from './code-execution-node'
import { TemplateTransformNode, TemplateTransformNodeInfo, TemplateTransformNodeDefaultData } from './template-transform-node'
import { VariableAggregatorNode, VariableAggregatorNodeInfo, VariableAggregatorNodeDefaultData } from './variable-aggregator-node'
import { DocumentExtractorNode, DocumentExtractorNodeInfo, DocumentExtractorNodeDefaultData } from './document-extractor-node'
import { VariableAssignmentNode, VariableAssignmentNodeInfo, VariableAssignmentNodeDefaultData } from './variable-assignment-node'
import { ParameterExtractorNode, ParameterExtractorNodeInfo, ParameterExtractorNodeDefaultData } from './parameter-extractor-node'
import { EndNode, EndNodeInfo, EndNodeDefaultData } from './end-node'

// Node type mapping.
export const nodeTypes = {
  'text-node': TextNode,
  'prompt-node': PromptNode,
  'llm-node': LLMNode,
  'tool-node': ToolNode,
  'data-node': DataNode,
  'output-node': OutputNode,
  'knowledge-search-node': KnowledgeSearchNode,
  'agent-node': AgentNode,
  'question-classifier-node': QuestionClassifierNode,
  'logic-node': LogicNode,
  'conditional-node': ConditionalNode,
  'delivery-node': DeliveryNode,
  'loop-node': LoopNode,
  'transform-node': TransformNode,
  'code-execution-node': CodeExecutionNode,
  'template-transform-node': TemplateTransformNode,
  'variable-aggregator-node': VariableAggregatorNode,
  'document-extractor-node': DocumentExtractorNode,
  'variable-assignment-node': VariableAssignmentNode,
  'parameter-extractor-node': ParameterExtractorNode,
  'end-node': EndNode,
}

// Node metadata mapping.
export const nodeTypeInfo = {
  'text-node': TextNodeInfo,
  'prompt-node': PromptNodeInfo,
  'llm-node': LLMNodeInfo,
  'tool-node': ToolNodeInfo,
  'data-node': DataNodeInfo,
  'output-node': OutputNodeInfo,
  'knowledge-search-node': KnowledgeSearchNodeInfo,
  'agent-node': AgentNodeInfo,
  'question-classifier-node': QuestionClassifierNodeInfo,
  'logic-node': LogicNodeInfo,
  'conditional-node': ConditionalNodeInfo,
  'delivery-node': DeliveryNodeInfo,
  'loop-node': LoopNodeInfo,
  'transform-node': TransformNodeInfo,
  'code-execution-node': CodeExecutionNodeInfo,
  'template-transform-node': TemplateTransformNodeInfo,
  'variable-aggregator-node': VariableAggregatorNodeInfo,
  'document-extractor-node': DocumentExtractorNodeInfo,
  'variable-assignment-node': VariableAssignmentNodeInfo,
  'parameter-extractor-node': ParameterExtractorNodeInfo,
  'end-node': EndNodeInfo,
}


// Properties panel mapping.
export const propertyPanels = {
  'text-node': TextProperties,
  'prompt-node': PromptProperties,
  'llm-node': LLMProperties,
  'tool-node': ToolProperties,
  'data-node': DataProperties,
  'output-node': OutputProperties,
  'knowledge-search-node': KnowledgeSearchProperties,
  'agent-node': AgentProperties,
  'question-classifier-node': QuestionClassifierProperties,
  // Other node panels can be added as needed.
}

// Default node data.
export const getDefaultNodeData = (type: string) => {
  switch (type) {
    case 'text-node':
      return TextNodeDefaultData
    case 'prompt-node':
      return PromptNodeDefaultData
    case 'llm-node':
      return LLMNodeDefaultData
    case 'tool-node':
      return ToolNodeDefaultData
    case 'data-node':
      return DataNodeDefaultData
    case 'output-node':
      return OutputNodeDefaultData
    case 'knowledge-search-node':
      return KnowledgeSearchNodeDefaultData
    case 'agent-node':
      return AgentNodeDefaultData // Use AgentNodeDefaultData.
    case 'question-classifier-node':
      return QuestionClassifierNodeDefaultData
    case 'logic-node':
      return LogicNodeDefaultData
    case 'conditional-node':
      return ConditionalNodeDefaultData
    case 'delivery-node':
      return DeliveryNodeDefaultData
    case 'loop-node':
      return LoopNodeDefaultData
    case 'transform-node':
      return TransformNodeDefaultData
    case 'code-execution-node':
      return CodeExecutionNodeDefaultData
    case 'template-transform-node':
      return TemplateTransformNodeDefaultData
    case 'variable-aggregator-node':
      return VariableAggregatorNodeDefaultData
    case 'document-extractor-node':
      return DocumentExtractorNodeDefaultData
    case 'variable-assignment-node':
      return VariableAssignmentNodeDefaultData
    case 'parameter-extractor-node':
      return ParameterExtractorNodeDefaultData
    case 'end-node':
      return EndNodeDefaultData
    default:
      return {}
  }
}


// Node categories.
export const nodeCategories = [
  {
    id: 'input',
    label: 'Input',
    types: ['text-node', 'prompt-node'],
  },
  {
    id: 'model',
    label: 'Model',
    types: ['llm-node', 'agent-node'],
  },
  {
    id: 'tool',
    label: 'Tool',
    types: [
      'tool-node',
      'knowledge-search-node',
      'question-classifier-node',
      'transform-node',
      'code-execution-node',
      'template-transform-node'
    ],
  },
  {
    id: 'data',
    label: 'Data',
    types: [
      'data-node',
      'variable-aggregator-node',
      'document-extractor-node',
      'variable-assignment-node',
      'parameter-extractor-node'
    ],
  },
  {
    id: 'flow',
    label: 'Flow',
    types: [
      'logic-node',
      'conditional-node',
      'delivery-node',
      'loop-node',
      'end-node'
    ],
  },
  {
    id: 'output',
    label: 'Output',
    types: ['output-node'],
  },
]
