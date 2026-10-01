import type { DatasetCase, DatasetCaseInput, ExpectedFeatures } from '@/services/evaluation-service'

/**
 * The case editor's form state and its translation to and from the dataset
 * case format (`kernel/specs/v1/dataset_case_spec`). Kept apart from the
 * components so the rules the server will enforce are checked in one place
 * before a request is made, and can be tested without rendering.
 */
export interface CaseFormState {
  name: string
  /** `text` sends the input as a string; `json` stores an object, such as `messages`. */
  inputMode: 'text' | 'json'
  input: string
  /** One term per line. */
  terms: string
  maxLatency: string
  maxCost: string
  judge: boolean
  rubric: string
  minScore: string
  judgeModel: string
}

export const EMPTY_CASE_FORM: CaseFormState = {
  name: '',
  inputMode: 'text',
  input: '',
  terms: '',
  maxLatency: '',
  maxCost: '',
  judge: false,
  rubric: '',
  minScore: '0.7',
  judgeModel: '',
}

/** Why a form cannot become a case; the editor shows the matching message. */
export type CaseFormError =
  'name' | 'input' | 'inputJson' | 'noExpectation' | 'latency' | 'cost' | 'rubric' | 'score'

export function caseToForm(item: DatasetCase): CaseFormState {
  const features = item.expected_features_json || {}
  const judge = features.llm_judge
  return {
    name: item.name,
    inputMode: typeof item.input === 'string' ? 'text' : 'json',
    input: typeof item.input === 'string' ? item.input : JSON.stringify(item.input, null, 2),
    terms: (features.minimum_output_terms || []).join('\n'),
    maxLatency: features.max_latency_ms != null ? String(features.max_latency_ms) : '',
    maxCost: features.max_cost_amount != null ? String(features.max_cost_amount) : '',
    judge: Boolean(judge),
    rubric: judge?.rubric || '',
    minScore: judge?.min_score != null ? String(judge.min_score) : EMPTY_CASE_FORM.minScore,
    judgeModel: judge?.model || '',
  }
}

export function formToCase(
  form: CaseFormState,
): { ok: true; value: DatasetCaseInput } | { ok: false; error: CaseFormError } {
  const name = form.name.trim()
  if (!name) return { ok: false, error: 'name' }

  let input: string | Record<string, unknown>
  if (form.inputMode === 'json') {
    try {
      const parsed: unknown = JSON.parse(form.input)
      if (
        !parsed ||
        typeof parsed !== 'object' ||
        Array.isArray(parsed) ||
        !Object.keys(parsed).length
      ) {
        return { ok: false, error: 'inputJson' }
      }
      input = parsed as Record<string, unknown>
    } catch {
      return { ok: false, error: 'inputJson' }
    }
  } else {
    if (!form.input.trim()) return { ok: false, error: 'input' }
    input = form.input
  }

  const features: ExpectedFeatures = {}
  const terms = form.terms
    .split('\n')
    .map((term) => term.trim())
    .filter(Boolean)
  if (terms.length) features.minimum_output_terms = terms
  if (form.maxLatency.trim()) {
    const latency = Number(form.maxLatency)
    if (!Number.isInteger(latency) || latency < 1) return { ok: false, error: 'latency' }
    features.max_latency_ms = latency
  }
  if (form.maxCost.trim()) {
    const cost = Number(form.maxCost)
    if (!Number.isFinite(cost) || cost < 0) return { ok: false, error: 'cost' }
    features.max_cost_amount = cost
  }
  if (form.judge) {
    const rubric = form.rubric.trim()
    if (!rubric) return { ok: false, error: 'rubric' }
    const judge: NonNullable<ExpectedFeatures['llm_judge']> = { rubric }
    if (form.minScore.trim()) {
      const score = Number(form.minScore)
      if (!Number.isFinite(score) || score < 0 || score > 1) return { ok: false, error: 'score' }
      judge.min_score = score
    }
    if (form.judgeModel.trim()) judge.model = form.judgeModel.trim()
    features.llm_judge = judge
  }
  // A case that asserts nothing passes whatever the agent says.
  if (!Object.keys(features).length) return { ok: false, error: 'noExpectation' }

  return { ok: true, value: { name, input, expected_features: features } }
}

/** A case's input on one line for a table cell. */
export function inputPreview(input: DatasetCase['input'], max = 120): string {
  const text = typeof input === 'string' ? input : JSON.stringify(input)
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat
}

/** The first twelve hex digits of a content hash: enough to tell revisions apart. */
export function shortHash(hash: string): string {
  return hash.slice(0, 12)
}

/** Whether a failure reason is the judge's, so the report can show its score beside it. */
export function isJudgeFailure(reason: string): boolean {
  return reason.startsWith('llm_judge')
}
