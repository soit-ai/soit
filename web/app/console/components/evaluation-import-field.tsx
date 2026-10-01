import { useRef, useState } from 'react'

import { ConsoleButton } from './button'
import { useTranslation } from '@/i18n'
import {
  IMPORT_MAX_BYTES,
  IMPORT_MAX_LINES,
  type ImportLineError,
} from '@/services/evaluation-service'

/** The cases a pasted or chosen JSONL text holds, as the server will count them. */
export function countImportLines(content: string): number {
  return content.split('\n').filter((line) => line.trim()).length
}

/**
 * The JSONL half of a dataset import: a text area to paste into, a file to
 * read, and the lines the server refused. A failed import refuses the whole
 * file, so every bad line is listed with its number rather than one at a time.
 */
export function EvaluationImportField({
  content,
  onContent,
  errors,
  required,
}: {
  content: string
  onContent: (content: string) => void
  errors: ImportLineError[]
  /** Whether the dialog cannot be confirmed without cases. */
  required?: boolean
}) {
  const { t } = useTranslation()
  const fileInput = useRef<HTMLInputElement>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const lines = countImportLines(content)

  const onFile = async (file: File | undefined) => {
    setFileError(null)
    if (!file) return
    if (file.size > IMPORT_MAX_BYTES) {
      setFileError(
        t('console.evaluations.import.tooLarge', { max: IMPORT_MAX_BYTES / (1024 * 1024) }),
      )
      return
    }
    onContent(await file.text())
  }

  return (
    <>
      <div className="mrow">
        <label htmlFor="evaluation-import-content">
          {t('console.evaluations.import.label')}
          {!required && <small>{t('console.evaluations.import.optional')}</small>}
          <small>{t('console.evaluations.import.format')}</small>
        </label>
        <div style={{ display: 'grid', gap: 6 }}>
          <textarea
            id="evaluation-import-content"
            className="input"
            rows={7}
            spellCheck={false}
            value={content}
            placeholder={t('console.evaluations.import.placeholder')}
            onChange={(event) => onContent(event.target.value)}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              ref={fileInput}
              type="file"
              accept=".jsonl,.ndjson,.json,.txt,application/x-ndjson"
              style={{ display: 'none' }}
              aria-label={t('console.evaluations.import.chooseFile')}
              onChange={(event) => {
                void onFile(event.target.files?.[0])
                event.target.value = ''
              }}
            />
            <ConsoleButton size="sm" onClick={() => fileInput.current?.click()}>
              {t('console.evaluations.import.chooseFile')}
            </ConsoleButton>
            <span className="mono dimmer" style={{ fontSize: 11 }}>
              {t('console.evaluations.import.count', { count: lines, max: IMPORT_MAX_LINES })}
            </span>
          </div>
          {lines > IMPORT_MAX_LINES && (
            <span style={{ color: 'var(--danger-foreground)', fontSize: 11.5 }}>
              {t('console.evaluations.import.tooMany', { max: IMPORT_MAX_LINES })}
            </span>
          )}
          {fileError && (
            <span style={{ color: 'var(--danger-foreground)', fontSize: 11.5 }}>{fileError}</span>
          )}
        </div>
      </div>
      {errors.length > 0 && (
        <div className="mrow">
          <label>{t('console.evaluations.import.errors')}</label>
          <ul
            className="mono"
            role="alert"
            style={{
              margin: 0,
              padding: 0,
              listStyle: 'none',
              display: 'grid',
              gap: 3,
              fontSize: 11,
              maxHeight: 160,
              overflow: 'auto',
              color: 'var(--danger-foreground)',
            }}
          >
            {errors.map((error, index) => (
              <li key={`${error.line ?? 'file'}-${index}`} style={{ overflowWrap: 'anywhere' }}>
                {error.line != null
                  ? t('console.evaluations.import.lineError', {
                      line: error.line,
                      message: error.message,
                    })
                  : error.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
