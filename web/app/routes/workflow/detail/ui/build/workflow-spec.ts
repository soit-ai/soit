import type { Edge, Node } from '@xyflow/react'
import {
  builderTypeByRuntimeType,
  isCanonicalBuilderType,
  isCanonicalRuntimeType,
  runtimeTypeByBuilderType,
  type CanonicalBuilderType,
  type CanonicalRuntimeType,
} from './canonical-node-registry'

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }

const canonicalUiMetadata = Symbol('canonicalUiMetadata')

const canonicalParamKeysByRuntimeType: Record<CanonicalRuntimeType, readonly string[]> = {
  input: ['select'],
  transform: ['mapping'],
  set_var: ['key', 'value'],
  llm: ['model', 'prompt', 'system', 'temperature', 'max_tokens'],
  retrieve: ['knowledge_ref', 'query', 'top_k', 'filters', 'rerank_model'],
  tool: ['tool_ref', 'arguments', 'input'],
  condition: ['condition'],
  output: ['value'],
}

type RuntimeNode = {
  id: string
  type: CanonicalRuntimeType
  name: string
  params: Record<string, JsonValue>
  ui: {
    [key: string]: unknown
    position: { x: number; y: number }
    builder_type: CanonicalBuilderType
    data: Record<string, unknown>
  }
}

type RuntimeEdge = {
  id: string
  from: string
  to: string
  from_port?: string | null
  to_port?: string | null
  condition?: string
}

type PersistedFromPort =
  | { present: false }
  | { present: true; value: string | null }

export type WorkflowSpec = {
  name: string
  version?: string | null
  description?: string
  inputs_schema: Record<string, unknown>
  outputs_schema: Record<string, unknown>
  limits?: Record<string, unknown> | null
  runtime?: Record<string, unknown> | null
  policy?: Record<string, unknown> | null
  semantics?: Record<string, unknown> | null
  graph: { nodes: Record<string, any>[]; edges: Record<string, any>[] }
}

export type WorkflowSpecBase = Pick<
  WorkflowSpec,
  'version' | 'inputs_schema' | 'outputs_schema' | 'limits' | 'runtime' | 'policy' | 'semantics'
>

export type ParsedWorkflowVersion = {
  name: string
  description: string
  base: WorkflowSpecBase
  nodes: Node[]
  edges: Edge[]
  hasUnsupportedNodes: boolean
}

type WorkflowVersionLike = {
  graph_json?: Record<string, any> | null
} | null

export class UnsupportedBuilderNodeError extends Error {
  readonly nodeId: string
  readonly nodeType: string | undefined

  constructor(nodeId: string, nodeType: string | undefined) {
    super(`Node "${nodeId}" has unsupported builder type "${nodeType || 'missing'}".`)
    this.name = 'UnsupportedBuilderNodeError'
    this.nodeId = nodeId
    this.nodeType = nodeType
  }
}

export class CanonicalNodeValidationError extends Error {
  readonly nodeId: string
  readonly nodeType: CanonicalBuilderType
  readonly field: string

  constructor(nodeId: string, nodeType: CanonicalBuilderType, field: string, message: string) {
    super(`Node "${nodeId}" (${nodeType}) has invalid field "${field}": ${message}`)
    this.name = 'CanonicalNodeValidationError'
    this.nodeId = nodeId
    this.nodeType = nodeType
    this.field = field
  }
}

export class UnsupportedWorkflowEdgeError extends Error {
  readonly edgeId: string
  readonly condition: unknown

  constructor(edgeId: string, condition: unknown, compatibilityKind?: string) {
    super(compatibilityKind === 'unsupported-condition'
      ? `Edge "${edgeId}" has an unsupported persisted condition and cannot be saved safely.`
      : `Edge "${edgeId}" has unsupported persisted data and cannot be saved safely.`)
    this.name = 'UnsupportedWorkflowEdgeError'
    this.edgeId = edgeId
    this.condition = condition
  }
}

const hasOwn = (value: object, key: PropertyKey) => Object.prototype.hasOwnProperty.call(value, key)

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const isDensePlainArray = (value: unknown): value is unknown[] => {
  if (
    !Array.isArray(value)
    || Object.getPrototypeOf(value) !== Array.prototype
    || Object.keys(value).length !== value.length
  ) {
    return false
  }
  for (let index = 0; index < value.length; index += 1) {
    if (!hasOwn(value, index)) {
      return false
    }
  }
  return true
}

const isJsonValue = (value: unknown, seen = new Set<object>()): value is JsonValue => {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') {
    return true
  }
  if (typeof value === 'number') {
    return Number.isFinite(value)
  }
  if (typeof value !== 'object') {
    return false
  }
  if (seen.has(value)) {
    return false
  }

  seen.add(value)
  let valid: boolean
  if (Array.isArray(value)) {
    valid = isDensePlainArray(value)
    for (let index = 0; valid && index < value.length; index += 1) {
      valid = isJsonValue(value[index], seen)
    }
  } else {
    const prototype = Object.getPrototypeOf(value)
    valid = (prototype === Object.prototype || prototype === null)
      && Object.values(value).every((item) => isJsonValue(item, seen))
  }
  seen.delete(value)
  return valid
}

const dataValue = (data: Record<string, unknown>, ...keys: string[]): unknown => {
  for (const key of keys) {
    if (hasOwn(data, key)) {
      return data[key]
    }
  }
  return undefined
}

const invalidField = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  message: string
): never => {
  throw new CanonicalNodeValidationError(node.id, nodeType, field, message)
}

const requireNonEmptyString = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  value: unknown
): string => {
  if (typeof value !== 'string' || !value.trim()) {
    return invalidField(node, nodeType, field, 'a non-empty string is required')
  }
  return value
}

const requireString = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  value: unknown
): string => {
  if (typeof value !== 'string') {
    return invalidField(node, nodeType, field, 'a string is required')
  }
  return value
}

const requireJsonValue = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  value: unknown
): JsonValue => {
  if (!isJsonValue(value)) {
    return invalidField(node, nodeType, field, 'a JSON value or expression is required')
  }
  return value
}

const optionalString = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  value: unknown
): string | undefined => {
  if (value === undefined) {
    return undefined
  }
  if (typeof value !== 'string') {
    return invalidField(node, nodeType, field, 'must be a string when present')
  }
  return value
}

const optionalNumber = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  value: unknown
): number | undefined => {
  if (value === undefined) {
    return undefined
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return invalidField(node, nodeType, field, 'must be a finite number when present')
  }
  return value
}

const optionalJsonValue = (
  node: Node,
  nodeType: CanonicalBuilderType,
  field: string,
  value: unknown
): JsonValue | undefined => {
  if (value === undefined) {
    return undefined
  }
  return requireJsonValue(node, nodeType, field, value)
}

const runtimeParamsForNode = (
  node: Node,
  nodeType: CanonicalBuilderType,
  data: Record<string, unknown>
): Record<string, JsonValue> => {
  switch (nodeType) {
    case 'input-node': {
      const select = dataValue(data, 'select')
      if (select === undefined) {
        return {}
      }
      if (!isDensePlainArray(select) || !select.every((item) => typeof item === 'string')) {
        return invalidField(node, nodeType, 'select', 'must be an array of strings when present')
      }
      return { select }
    }
    case 'transform-node': {
      const mapping = dataValue(data, 'mapping')
      if (!isRecord(mapping) || !isJsonValue(mapping)) {
        return invalidField(node, nodeType, 'mapping', 'a JSON object is required')
      }
      return { mapping }
    }
    case 'variable-assignment-node':
      return {
        key: requireNonEmptyString(node, nodeType, 'key', dataValue(data, 'variableName', 'key')),
        value: requireJsonValue(node, nodeType, 'value', dataValue(data, 'variableValue', 'value')),
      }
    case 'llm-node': {
      const params: Record<string, JsonValue> = {
        model: requireNonEmptyString(node, nodeType, 'model', dataValue(data, 'modelName', 'model')),
        prompt: requireString(node, nodeType, 'prompt', dataValue(data, 'prompt')),
      }
      const system = optionalString(node, nodeType, 'system', dataValue(data, 'systemPrompt', 'system'))
      const temperature = optionalNumber(node, nodeType, 'temperature', dataValue(data, 'temperature'))
      const maxTokens = optionalNumber(node, nodeType, 'max_tokens', dataValue(data, 'maxTokens', 'max_tokens'))
      if (system !== undefined) params.system = system
      if (temperature !== undefined) params.temperature = temperature
      if (maxTokens !== undefined) params.max_tokens = maxTokens
      return params
    }
    case 'knowledge-search-node': {
      const params: Record<string, JsonValue> = {
        knowledge_ref: requireNonEmptyString(
          node,
          nodeType,
          'knowledge_ref',
          dataValue(data, 'customSource', 'knowledgeRef', 'knowledge_ref')
        ),
        query: requireString(node, nodeType, 'query', dataValue(data, 'query')),
      }
      const topK = optionalNumber(node, nodeType, 'top_k', dataValue(data, 'topK', 'top_k'))
      const filters = optionalJsonValue(node, nodeType, 'filters', dataValue(data, 'filters'))
      const rerankModel = optionalString(
        node,
        nodeType,
        'rerank_model',
        dataValue(data, 'rerankModel', 'rerank_model')
      )
      if (topK !== undefined) params.top_k = topK
      if (filters !== undefined) params.filters = filters
      if (rerankModel !== undefined) params.rerank_model = rerankModel
      return params
    }
    case 'tool-node': {
      const params: Record<string, JsonValue> = {
        tool_ref: requireNonEmptyString(node, nodeType, 'tool_ref', dataValue(data, 'toolName', 'toolRef', 'tool_ref')),
      }
      const args = optionalJsonValue(node, nodeType, 'arguments', dataValue(data, 'parameters', 'arguments'))
      const input = optionalJsonValue(node, nodeType, 'input', dataValue(data, 'input'))
      if (args !== undefined) params.arguments = args
      if (input !== undefined) params.input = input
      return params
    }
    case 'conditional-node': {
      const condition = dataValue(data, 'condition', 'expression')
      if (typeof condition !== 'string' && typeof condition !== 'boolean') {
        return invalidField(node, nodeType, 'condition', 'a string expression or boolean is required')
      }
      return { condition }
    }
    case 'output-node':
      return {
        value: requireJsonValue(node, nodeType, 'value', dataValue(data, 'value')),
      }
  }
}

export const serializeCanonicalNode = (node: Node): RuntimeNode => {
  if (!isCanonicalBuilderType(node.type)) {
    throw new UnsupportedBuilderNodeError(node.id, node.type)
  }

  const data = isRecord(node.data) ? node.data : {}
  const label = typeof data.label === 'string' && data.label.trim() ? data.label : node.id
  const originalUiValue = (data as Record<PropertyKey, unknown>)[canonicalUiMetadata]
  const originalUi = isRecord(originalUiValue) ? originalUiValue : {}
  const serializedUiData = Object.fromEntries(Object.entries(data))

  return {
    id: node.id,
    type: runtimeTypeByBuilderType[node.type],
    name: label,
    params: runtimeParamsForNode(node, node.type, data),
    ui: {
      ...originalUi,
      position: { ...node.position },
      builder_type: node.type,
      data: serializedUiData,
    },
  }
}

export const conditionForEdge = (edge: Edge, sourceRuntimeType: CanonicalRuntimeType | undefined): string | undefined => {
  if (sourceRuntimeType !== 'condition') {
    return undefined
  }

  const edgeData = isRecord(edge.data) ? edge.data : {}
  const hasRestoredSourceHandle = hasOwn(edgeData, 'restoredSourceHandle')
  if (
    edgeData.persistedConditionEmpty === true
    && (!hasRestoredSourceHandle || edge.sourceHandle === edgeData.restoredSourceHandle)
  ) {
    return undefined
  }

  const resultRef = `{{ steps.${edge.source}.output.result }}`
  if (edge.sourceHandle === 'false' || edge.sourceHandle === 'output-false') {
    return `${resultRef} == false`
  }
  if (edge.sourceHandle === 'true' || edge.sourceHandle === 'output-true') {
    return resultRef
  }
  return undefined
}

const persistedFromPortForUnchangedEdge = (edge: Edge): PersistedFromPort | undefined => {
  const edgeData = isRecord(edge.data) ? edge.data : {}
  if (!hasOwn(edgeData, 'restoredSourceHandle') || edge.sourceHandle !== edgeData.restoredSourceHandle) {
    return undefined
  }

  const persistedFromPort = edgeData.persistedFromPort
  if (!isRecord(persistedFromPort) || typeof persistedFromPort.present !== 'boolean') {
    return undefined
  }
  if (!persistedFromPort.present) {
    return { present: false }
  }
  if (typeof persistedFromPort.value === 'string' || persistedFromPort.value === null) {
    return { present: true, value: persistedFromPort.value }
  }
  return undefined
}

export const serializeWorkflowSpec = (
  base: WorkflowSpecBase,
  name: string,
  description: string,
  nodes: Node[],
  edges: Edge[]
): WorkflowSpec => {
  const serializedNodes = nodes.map(serializeCanonicalNode)
  const runtimeTypeByNodeId = new Map(serializedNodes.map((node) => [node.id, node.type]))
  const serializedEdges: RuntimeEdge[] = edges.map((edge) => {
    const edgeData = isRecord(edge.data) ? edge.data : {}
    if (edgeData.unsupported === true) {
      throw new UnsupportedWorkflowEdgeError(
        edge.id,
        edgeData.originalCondition ?? edgeData.originalEdge,
        typeof edgeData.compatibilityKind === 'string' ? edgeData.compatibilityKind : undefined
      )
    }

    const serializedEdge: RuntimeEdge = {
      id: edge.id,
      from: edge.source,
      to: edge.target,
    }
    const persistedFromPort = persistedFromPortForUnchangedEdge(edge)
    if (persistedFromPort?.present) {
      serializedEdge.from_port = persistedFromPort.value
    } else if (!persistedFromPort && edge.sourceHandle !== undefined) {
      serializedEdge.from_port = edge.sourceHandle
    }
    if (edge.targetHandle !== undefined) {
      serializedEdge.to_port = edge.targetHandle
    }
    const condition = conditionForEdge(edge, runtimeTypeByNodeId.get(edge.source))
    if (condition !== undefined) {
      serializedEdge.condition = condition
    }
    return serializedEdge
  })

  return {
    name,
    version: base.version,
    description: description.trim() ? description : undefined,
    inputs_schema: base.inputs_schema,
    outputs_schema: base.outputs_schema,
    limits: base.limits,
    runtime: base.runtime,
    policy: base.policy,
    semantics: base.semantics,
    graph: {
      nodes: serializedNodes,
      edges: serializedEdges,
    },
  }
}

const validPosition = (value: unknown): value is { x: number; y: number } => {
  return isRecord(value) && typeof value.x === 'number' && typeof value.y === 'number'
}

const presentationLabel = (uiData: Record<string, unknown>, rawNode: Record<string, unknown>, id: string) => {
  if (typeof uiData.label === 'string' && uiData.label.trim()) {
    return uiData.label
  }
  if (typeof rawNode.name === 'string' && rawNode.name.trim()) {
    return rawNode.name
  }
  return id
}

const paramDataForBuilder = (
  builderType: CanonicalBuilderType,
  params: Record<string, unknown>
): Record<string, unknown> => {
  const param = (key: string) => hasOwn(params, key) ? params[key] : undefined

  switch (builderType) {
    case 'input-node':
      return { select: param('select') }
    case 'transform-node':
      return { mapping: param('mapping') }
    case 'variable-assignment-node':
      return { variableName: param('key'), variableValue: param('value') }
    case 'llm-node':
      return {
        modelName: param('model'),
        prompt: param('prompt'),
        systemPrompt: param('system'),
        temperature: param('temperature'),
        maxTokens: param('max_tokens'),
      }
    case 'knowledge-search-node':
      return {
        knowledgeRef: param('knowledge_ref'),
        customSource: param('knowledge_ref'),
        dataSource: typeof param('knowledge_ref') === 'string' ? 'custom' : undefined,
        query: param('query'),
        topK: param('top_k'),
        filters: param('filters'),
        rerankModel: param('rerank_model'),
      }
    case 'tool-node':
      return { toolName: param('tool_ref'), parameters: param('arguments'), input: param('input') }
    case 'conditional-node':
      return { condition: param('condition') }
    case 'output-node':
      return { value: param('value') }
  }
}

const compatibilityNode = (
  rawNode: Record<string, unknown>,
  index: number,
  reason: string,
  originalNode: unknown = rawNode
): Node => {
  const id = typeof rawNode.id === 'string' ? rawNode.id : `unsupported-${index}`
  const rawUi = isRecord(rawNode.ui) ? rawNode.ui : {}
  const rawUiData = isRecord(rawUi.data) ? rawUi.data : {}
  const originalRuntimeType = rawNode.type
  const originalBuilderType = hasOwn(rawUi, 'builder_type') ? rawUi.builder_type : undefined
  const position = validPosition(rawUi.position) ? { ...rawUi.position } : { x: 120 + index * 240, y: 140 }

  return {
    id,
    type: 'compatibility-node',
    position,
    data: {
      ...rawUiData,
      label: presentationLabel(rawUiData, rawNode, id),
      unsupported: true,
      validationError: reason,
      originalId: rawNode.id,
      originalName: rawNode.name,
      originalRuntimeType,
      originalBuilderType,
      originalParams: rawNode.params,
      originalUi: rawNode.ui,
      originalUiData: rawUi.data,
      originalNode,
    },
  }
}

const parseNode = (rawNodeValue: unknown, index: number): Node => {
  if (!isRecord(rawNodeValue)) {
    return compatibilityNode({}, index, 'Persisted workflow node is not an object.', rawNodeValue)
  }

  const rawNode = rawNodeValue
  const id = typeof rawNode.id === 'string' ? rawNode.id : `unsupported-${index}`
  const runtimeType = rawNode.type

  if (!isCanonicalRuntimeType(runtimeType)) {
    return compatibilityNode(rawNode, index, `Runtime type "${String(runtimeType)}" is not supported by the canonical builder.`)
  }

  if (hasOwn(rawNode, 'ui') && rawNode.ui !== null && !isRecord(rawNode.ui)) {
    return compatibilityNode(rawNode, index, 'Persisted node ui must be an object or null when present.')
  }
  const rawUi = isRecord(rawNode.ui) ? rawNode.ui : {}

  if (hasOwn(rawUi, 'builder_type') && typeof rawUi.builder_type !== 'string') {
    return compatibilityNode(rawNode, index, 'Persisted ui.builder_type must be a string when present.')
  }
  const persistedBuilderType = hasOwn(rawUi, 'builder_type') ? rawUi.builder_type as string : undefined
  const expectedBuilderType = builderTypeByRuntimeType[runtimeType]
  if (persistedBuilderType !== undefined && !isCanonicalBuilderType(persistedBuilderType)) {
    return compatibilityNode(rawNode, index, `Builder type "${persistedBuilderType}" is not canonical.`)
  }
  if (persistedBuilderType !== undefined && persistedBuilderType !== expectedBuilderType) {
    return compatibilityNode(
      rawNode,
      index,
      `Builder type "${persistedBuilderType}" does not match runtime type "${runtimeType}".`
    )
  }

  if (hasOwn(rawNode, 'params') && !isRecord(rawNode.params)) {
    return compatibilityNode(rawNode, index, 'Persisted node params must be an object when present.')
  }
  const params = isRecord(rawNode.params) ? rawNode.params : {}
  const unknownParamKeys = Object.keys(params).filter(
    (key) => !canonicalParamKeysByRuntimeType[runtimeType].includes(key)
  )
  if (unknownParamKeys.length) {
    return compatibilityNode(
      rawNode,
      index,
      `Runtime type "${runtimeType}" has unsupported params: ${unknownParamKeys.join(', ')}.`
    )
  }

  if (hasOwn(rawUi, 'data') && !isRecord(rawUi.data)) {
    return compatibilityNode(rawNode, index, 'Persisted ui.data must be an object when present.')
  }
  if (hasOwn(rawUi, 'position') && !validPosition(rawUi.position)) {
    return compatibilityNode(rawNode, index, 'Persisted ui.position must contain numeric x and y values when present.')
  }

  const builderType = persistedBuilderType ?? expectedBuilderType
  const uiData = isRecord(rawUi.data) ? rawUi.data : {}
  const position = validPosition(rawUi.position) ? { ...rawUi.position } : { x: 120 + index * 240, y: 140 }

  return {
    id,
    type: builderType,
    position,
    data: {
      ...uiData,
      label: presentationLabel(uiData, rawNode, id),
      ...paramDataForBuilder(builderType, params),
      [canonicalUiMetadata]: rawUi,
    },
  }
}

const conditionVisualHandle = (
  rawEdge: Record<string, unknown>,
  sourceRuntimeType: unknown
): 'output-true' | 'output-false' | undefined => {
  if (sourceRuntimeType !== 'condition') {
    return undefined
  }

  const source = typeof rawEdge.from === 'string' ? rawEdge.from : ''
  const resultRef = `{{ steps.${source}.output.result }}`
  if (rawEdge.condition === resultRef) return 'output-true'
  if (rawEdge.condition === `${resultRef} == false`) return 'output-false'
  if (rawEdge.condition === 'true' || rawEdge.condition === true || rawEdge.condition === 'output-true') {
    return 'output-true'
  }
  if (rawEdge.condition === 'false' || rawEdge.condition === false || rawEdge.condition === 'output-false') {
    return 'output-false'
  }
  return undefined
}

const restoredSourceHandle = (
  rawEdge: Record<string, unknown>,
  sourceRuntimeType: unknown
): string | null | undefined => {
  const inferredConditionHandle = conditionVisualHandle(rawEdge, sourceRuntimeType)
  if (inferredConditionHandle) {
    return inferredConditionHandle
  }
  if (!hasOwn(rawEdge, 'from_port')) {
    return undefined
  }
  if (rawEdge.from_port === null || typeof rawEdge.from_port !== 'string') {
    return rawEdge.from_port === null ? null : undefined
  }
  if (sourceRuntimeType === 'condition') {
    if (rawEdge.from_port === 'true' || rawEdge.from_port === 'output-true') return 'output-true'
    if (rawEdge.from_port === 'false' || rawEdge.from_port === 'output-false') return 'output-false'
  }
  return rawEdge.from_port
}

const isRecognizedPersistedCondition = (
  rawEdge: Record<string, unknown>,
  sourceRuntimeType: unknown
): boolean => {
  if (rawEdge.condition === undefined || rawEdge.condition === null) {
    return true
  }
  return conditionVisualHandle(rawEdge, sourceRuntimeType) !== undefined
}

const persistedEdgeValidationError = (rawEdge: Record<string, unknown>): string | undefined => {
  const allowedKeys = new Set(['id', 'from', 'to', 'from_port', 'to_port', 'condition'])
  const unknownKeys = Object.keys(rawEdge).filter((key) => !allowedKeys.has(key))
  if (unknownKeys.length) {
    return `Persisted workflow edge has unsupported keys: ${unknownKeys.join(', ')}.`
  }

  for (const key of ['id', 'from', 'to'] as const) {
    if (typeof rawEdge[key] !== 'string' || !rawEdge[key].trim()) {
      return `Persisted workflow edge ${key} must be a non-empty string.`
    }
  }
  for (const key of ['from_port', 'to_port'] as const) {
    if (hasOwn(rawEdge, key) && rawEdge[key] !== null && typeof rawEdge[key] !== 'string') {
      return `Persisted workflow edge ${key} must be a string or null when present.`
    }
  }
  if (
    hasOwn(rawEdge, 'condition')
    && rawEdge.condition !== null
    && typeof rawEdge.condition !== 'string'
    && typeof rawEdge.condition !== 'boolean'
  ) {
    return 'Persisted workflow edge condition must be a string, boolean, or null when present.'
  }
  return undefined
}

const parseEdge = (
  rawEdgeValue: unknown,
  index: number,
  runtimeTypeByNodeId: Map<string, unknown>
): Edge => {
  const rawEdgeIsRecord = isRecord(rawEdgeValue)
  const rawEdge = rawEdgeIsRecord ? rawEdgeValue : {}
  const id = typeof rawEdge.id === 'string' && rawEdge.id.trim() ? rawEdge.id : `edge-${index}`
  const source = typeof rawEdge.from === 'string' && rawEdge.from.trim() ? rawEdge.from : ''
  const target = typeof rawEdge.to === 'string' && rawEdge.to.trim() ? rawEdge.to : ''
  const sourceRuntimeType = runtimeTypeByNodeId.get(source)
  const sourceHandle = restoredSourceHandle(rawEdge, sourceRuntimeType)
  const targetHandle = hasOwn(rawEdge, 'to_port')
    && (typeof rawEdge.to_port === 'string' || rawEdge.to_port === null)
    ? rawEdge.to_port
    : undefined
  const preservedData: Record<string, unknown> = {}
  if (!rawEdgeIsRecord) {
    preservedData.unsupported = true
    preservedData.compatibilityKind = 'unsupported-edge'
    preservedData.validationError = 'Persisted workflow edge is not an object.'
    preservedData.originalEdge = rawEdgeValue
  } else {
    const validationError = persistedEdgeValidationError(rawEdge)
    if (validationError) {
      preservedData.unsupported = true
      preservedData.compatibilityKind = 'unsupported-edge'
      preservedData.validationError = validationError
      preservedData.originalEdge = rawEdgeValue
    } else {
      if (sourceRuntimeType === 'condition') {
        preservedData.persistedFromPort = hasOwn(rawEdge, 'from_port')
          ? { present: true, value: rawEdge.from_port }
          : { present: false }
        preservedData.restoredSourceHandle = sourceHandle
      }
      if (sourceRuntimeType === 'condition' && (rawEdge.condition === undefined || rawEdge.condition === null)) {
        preservedData.persistedConditionEmpty = true
        preservedData.originalEdge = rawEdgeValue
      } else if (!isRecognizedPersistedCondition(rawEdge, sourceRuntimeType)) {
        preservedData.unsupported = true
        preservedData.compatibilityKind = 'unsupported-condition'
        preservedData.validationError = 'Persisted edge condition cannot be mapped to a canonical condition branch.'
        preservedData.originalCondition = rawEdge.condition
        preservedData.originalEdge = rawEdgeValue
      }
    }
  }

  return {
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
    data: Object.keys(preservedData).length ? preservedData : undefined,
  }
}

const optionalEnvelopeRecord = (value: unknown): Record<string, unknown> | null | undefined => {
  if (value === null) return null
  return isRecord(value) ? value : undefined
}

export const parseWorkflowVersion = (version: WorkflowVersionLike): ParsedWorkflowVersion => {
  const spec = isRecord(version?.graph_json) ? version.graph_json : {}
  const graph = isRecord(spec.graph) ? spec.graph : {}
  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : []
  const rawEdges = Array.isArray(graph.edges) ? graph.edges : []
  const runtimeTypeByNodeId = new Map<string, unknown>()
  rawNodes.forEach((rawNode) => {
    if (isRecord(rawNode) && typeof rawNode.id === 'string') {
      runtimeTypeByNodeId.set(rawNode.id, rawNode.type)
    }
  })

  const nodes = rawNodes.map(parseNode)

  return {
    name: typeof spec.name === 'string' ? spec.name : '',
    description: typeof spec.description === 'string' ? spec.description : '',
    base: {
      version: typeof spec.version === 'string' || spec.version === null ? spec.version : undefined,
      inputs_schema: isRecord(spec.inputs_schema) ? spec.inputs_schema : {},
      outputs_schema: isRecord(spec.outputs_schema) ? spec.outputs_schema : {},
      limits: optionalEnvelopeRecord(spec.limits),
      runtime: optionalEnvelopeRecord(spec.runtime),
      policy: optionalEnvelopeRecord(spec.policy),
      semantics: optionalEnvelopeRecord(spec.semantics),
    },
    nodes,
    edges: rawEdges.map((edge, index) => parseEdge(edge, index, runtimeTypeByNodeId)),
    hasUnsupportedNodes: nodes.some((node) => node.type === 'compatibility-node'),
  }
}
