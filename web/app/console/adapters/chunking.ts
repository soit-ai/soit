/**
 * Chunking presets the console offers for a knowledge library.
 *
 * The ingest pipeline reads `chunking_json.chunk_size` and `chunk_overlap`,
 * both in characters, with 1000 / 200 as its defaults; a preset is a named
 * pair of them. A library whose stored pair matches no preset is shown as
 * "custom" and left as it is.
 */

export type ChunkingPreset = 'default' | 'fine' | 'coarse'

export const CHUNKING_PRESETS: Record<ChunkingPreset, { chunk_size: number; chunk_overlap: number }> = {
  default: { chunk_size: 1000, chunk_overlap: 200 },
  fine: { chunk_size: 500, chunk_overlap: 100 },
  coarse: { chunk_size: 2000, chunk_overlap: 200 },
}

export const CHUNKING_PRESET_KEYS = Object.keys(CHUNKING_PRESETS) as ChunkingPreset[]

/** The preset a stored chunking configuration matches, if any. */
export function chunkingPresetOf(chunking: Record<string, unknown> | undefined): ChunkingPreset | 'custom' {
  const size = chunking?.chunk_size
  const overlap = chunking?.chunk_overlap
  if (size === undefined && overlap === undefined) return 'default'
  for (const key of CHUNKING_PRESET_KEYS) {
    const preset = CHUNKING_PRESETS[key]
    if (preset.chunk_size === size && preset.chunk_overlap === overlap) return key
  }
  return 'custom'
}
