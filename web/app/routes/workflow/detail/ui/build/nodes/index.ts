import { InputNode, InputNodeDefaultData, InputNodeInfo, InputProperties } from './input-node'
import { TransformNode, TransformNodeDefaultData, TransformNodeInfo, TransformProperties } from './transform-node'
import {
  VariableAssignmentNode,
  VariableAssignmentNodeDefaultData,
  VariableAssignmentNodeInfo,
  VariableAssignmentProperties,
} from './variable-assignment-node'
import { LLMNode, LLMNodeDefaultData, LLMNodeInfo, LLMProperties } from './llm-node'
import {
  KnowledgeSearchNode,
  KnowledgeSearchNodeDefaultData,
  KnowledgeSearchNodeInfo,
  KnowledgeSearchProperties,
} from './knowledge-search-node'
import { ToolNode, ToolNodeDefaultData, ToolNodeInfo, ToolProperties } from './tool-node'
import { ConditionalNode, ConditionalNodeDefaultData, ConditionalNodeInfo, ConditionalProperties } from './conditional-node'
import { OutputNode, OutputNodeDefaultData, OutputNodeInfo, OutputProperties } from './output-node'
import { CompatibilityNode } from './compatibility-node'
import type { CanonicalBuilderType } from '../canonical-node-registry'

export const nodeTypes = {
  'input-node': InputNode,
  'transform-node': TransformNode,
  'variable-assignment-node': VariableAssignmentNode,
  'llm-node': LLMNode,
  'knowledge-search-node': KnowledgeSearchNode,
  'tool-node': ToolNode,
  'conditional-node': ConditionalNode,
  'output-node': OutputNode,
  'compatibility-node': CompatibilityNode,
}

export const nodeTypeInfo = {
  'input-node': InputNodeInfo,
  'transform-node': TransformNodeInfo,
  'variable-assignment-node': VariableAssignmentNodeInfo,
  'llm-node': LLMNodeInfo,
  'knowledge-search-node': KnowledgeSearchNodeInfo,
  'tool-node': ToolNodeInfo,
  'conditional-node': ConditionalNodeInfo,
  'output-node': OutputNodeInfo,
} satisfies Record<CanonicalBuilderType, {
  type: string
  label: string
  category: string
  description: string
  icon: string
} & Record<string, unknown>>

export const propertyPanels = {
  'input-node': InputProperties,
  'transform-node': TransformProperties,
  'variable-assignment-node': VariableAssignmentProperties,
  'llm-node': LLMProperties,
  'knowledge-search-node': KnowledgeSearchProperties,
  'tool-node': ToolProperties,
  'conditional-node': ConditionalProperties,
  'output-node': OutputProperties,
} satisfies Record<CanonicalBuilderType, React.ComponentType<any>>

const defaultNodeData = {
  'input-node': InputNodeDefaultData,
  'transform-node': TransformNodeDefaultData,
  'variable-assignment-node': VariableAssignmentNodeDefaultData,
  'llm-node': LLMNodeDefaultData,
  'knowledge-search-node': KnowledgeSearchNodeDefaultData,
  'tool-node': ToolNodeDefaultData,
  'conditional-node': ConditionalNodeDefaultData,
  'output-node': OutputNodeDefaultData,
} satisfies Record<CanonicalBuilderType, Record<string, unknown>>

export const getDefaultNodeData = (type: CanonicalBuilderType) => defaultNodeData[type]

export const nodeCategories = [
  { id: 'input', label: 'Input', types: ['input-node'] },
  { id: 'model', label: 'Model', types: ['llm-node'] },
  { id: 'tool', label: 'Tool', types: ['tool-node'] },
  { id: 'data', label: 'Data', types: ['knowledge-search-node', 'transform-node', 'variable-assignment-node'] },
  { id: 'flow', label: 'Flow', types: ['conditional-node'] },
  { id: 'output', label: 'Output', types: ['output-node'] },
] as const satisfies ReadonlyArray<{
  id: 'input' | 'model' | 'tool' | 'data' | 'flow' | 'output'
  label: string
  types: readonly CanonicalBuilderType[]
}>
