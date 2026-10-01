import { describe, expect, it } from 'vitest'

import type { DatasetCase } from '@/services/evaluation-service'

import {
  EMPTY_CASE_FORM,
  caseToForm,
  formToCase,
  inputPreview,
  shortHash,
  type CaseFormState,
} from './evaluations'

const form = (overrides: Partial<CaseFormState>): CaseFormState => ({
  ...EMPTY_CASE_FORM,
  name: 'refund-window',
  input: 'How long do refunds take?',
  terms: '14 days',
  ...overrides,
})

describe('evaluation case form', () => {
  it('builds a case from text input and every kind of expectation', () => {
    const result = formToCase(
      form({
        terms: ' 14 days \n\nrefund ',
        maxLatency: '2000',
        maxCost: '0.05',
        judge: true,
        rubric: 'States the window plainly',
        minScore: '0.8',
        judgeModel: 'model:judge',
      }),
    )

    expect(result).toEqual({
      ok: true,
      value: {
        name: 'refund-window',
        input: 'How long do refunds take?',
        expected_features: {
          minimum_output_terms: ['14 days', 'refund'],
          max_latency_ms: 2000,
          max_cost_amount: 0.05,
          llm_judge: { rubric: 'States the window plainly', min_score: 0.8, model: 'model:judge' },
        },
      },
    })
  })

  it('stores a JSON object input as an object', () => {
    const result = formToCase(
      form({ inputMode: 'json', input: '{"messages":[{"role":"user","content":"hi"}]}' }),
    )

    expect(result).toMatchObject({
      ok: true,
      value: { input: { messages: [{ role: 'user', content: 'hi' }] } },
    })
  })

  it.each([
    [{ name: '  ' }, 'name'],
    [{ input: '   ' }, 'input'],
    [{ inputMode: 'json' as const, input: '[1]' }, 'inputJson'],
    [{ inputMode: 'json' as const, input: '{not json' }, 'inputJson'],
    [{ inputMode: 'json' as const, input: '{}' }, 'inputJson'],
    [{ terms: '' }, 'noExpectation'],
    [{ maxLatency: '0' }, 'latency'],
    [{ maxLatency: '1.5' }, 'latency'],
    [{ maxCost: '-1' }, 'cost'],
    [{ judge: true, rubric: ' ' }, 'rubric'],
    [{ judge: true, rubric: 'ok', minScore: '2' }, 'score'],
  ])('refuses a form the server would refuse: %j', (overrides, error) => {
    expect(formToCase(form(overrides))).toEqual({ ok: false, error })
  })

  it('round trips a stored case through the form', () => {
    const stored: DatasetCase = {
      id: 'regcase_1',
      name: 'chat',
      input: { messages: [{ role: 'user', content: 'hi' }] },
      expected_features_json: {
        minimum_output_terms: ['hello'],
        max_latency_ms: 900,
        llm_judge: { rubric: 'Polite', min_score: 0.9 },
      },
      dataset: 'default',
      dataset_revision: 2,
      created_at: '2026-10-01T00:00:00Z',
    }

    const restored = formToCase(caseToForm(stored))

    expect(restored).toEqual({
      ok: true,
      value: {
        name: 'chat',
        input: stored.input,
        expected_features: stored.expected_features_json,
      },
    })
  })

  it('shows an input on one line and a hash as twelve digits', () => {
    expect(inputPreview('a\n  b')).toBe('a b')
    expect(inputPreview({ a: 1 })).toBe('{"a":1}')
    expect(inputPreview('x'.repeat(200), 10)).toHaveLength(10)
    expect(shortHash('0123456789abcdef0123')).toBe('0123456789ab')
  })
})
