export const canonicalBuilderTypes = [
  'input-node',
  'transform-node',
  'variable-assignment-node',
  'llm-node',
  'knowledge-search-node',
  'tool-node',
  'conditional-node',
  'output-node',
] as const

export type CanonicalBuilderType = (typeof canonicalBuilderTypes)[number]

export const runtimeTypeByBuilderType = {
  'input-node': 'input',
  'transform-node': 'transform',
  'variable-assignment-node': 'set_var',
  'llm-node': 'llm',
  'knowledge-search-node': 'retrieve',
  'tool-node': 'tool',
  'conditional-node': 'condition',
  'output-node': 'output',
} as const satisfies Record<CanonicalBuilderType, string>

export type CanonicalRuntimeType = (typeof runtimeTypeByBuilderType)[CanonicalBuilderType]

export const builderTypeByRuntimeType = Object.fromEntries(
  canonicalBuilderTypes.map((builderType) => [runtimeTypeByBuilderType[builderType], builderType])
) as Record<CanonicalRuntimeType, CanonicalBuilderType>

export const isCanonicalBuilderType = (value: unknown): value is CanonicalBuilderType => {
  return typeof value === 'string' && canonicalBuilderTypes.includes(value as CanonicalBuilderType)
}

export const isCanonicalRuntimeType = (value: unknown): value is CanonicalRuntimeType => {
  return typeof value === 'string' && Object.hasOwn(builderTypeByRuntimeType, value)
}
