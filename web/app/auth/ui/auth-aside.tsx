import { useTranslation } from '@/i18n'

/**
 * The right-hand column of the auth screens (v13 prototype).
 *
 * It deliberately carries no capability tiles. Four abstractions —
 * build / ground / orchestrate / observe — are claims any competitor could
 * make. What a run leaves behind is specific, true, and drawn with the same
 * chips the run detail page uses, so the first screen and the second read as
 * one product.
 */

interface EvidenceStep {
  title: string
  detail: string
  note: string
  tone?: 'ok' | 'pri'
}

function EvidenceList({ title, hint, steps }: { title: string; hint: string; steps: EvidenceStep[] }) {
  return (
    <div className="panel auth-evidence">
      <div className="panel-head">
        <h2>{title}</h2>
        <span className="hint">{hint}</span>
      </div>
      {steps.map((step) => (
        <div className="auth-ev-step" key={step.title}>
          <span className="auth-ev-rail">
            <i className={`auth-ev-dot ${step.tone || 'ok'}`} />
          </span>
          <span className="auth-ev-what">
            <b>{step.title}</b>
            <small>{step.detail}</small>
          </span>
          <span className="ct">{step.note}</span>
        </div>
      ))}
    </div>
  )
}

function Notes({ notes }: { notes: { text: string; color?: string }[] }) {
  return (
    <div className="auth-notes">
      {notes.map((note) => (
        <span className="auth-note" key={note.text}>
          <i style={note.color ? { background: note.color } : undefined} aria-hidden />
          {note.text}
        </span>
      ))}
    </div>
  )
}

export function SignInAside() {
  const { t } = useTranslation()
  return (
    <>
      <div className="auth-claim">
        <h2>{t('auth.aside.signIn.claim')}</h2>
        <p>{t('auth.aside.signIn.body')}</p>
      </div>

      <div className="panel auth-evidence">
        <div className="panel-head">
          <h2>{t('auth.aside.signIn.evidenceTitle')}</h2>
          <span className="hint">{t('auth.aside.signIn.evidenceHint')}</span>
        </div>
        <div className="auth-ev-run">
          <span className="runid">run_01J9KD84QF</span>
          <span className="who">support-triage · webhook</span>
          <span className="chip st-pass">
            <i aria-hidden />
            PASS
          </span>
        </div>
        {[
          {
            title: t('auth.aside.signIn.policy'),
            detail: t('auth.aside.signIn.policyDetail'),
            note: t('auth.aside.signIn.policyNote'),
            tone: 'pri' as const,
          },
          {
            title: t('auth.aside.signIn.tool'),
            detail: 'helpdesk-api · tickets.write',
            note: t('auth.aside.signIn.toolNote'),
          },
          {
            title: t('auth.aside.signIn.citations'),
            detail: t('auth.aside.signIn.citationsDetail'),
            note: t('auth.aside.signIn.citationsNote'),
          },
          {
            title: t('auth.aside.signIn.audit'),
            detail: 'aud_8811 · retained',
            note: t('auth.aside.signIn.auditNote'),
          },
        ].map((step) => (
          <div className="auth-ev-step" key={step.title}>
            <span className="auth-ev-rail">
              <i className={`auth-ev-dot ${step.tone || 'ok'}`} />
            </span>
            <span className="auth-ev-what">
              <b>{step.title}</b>
              <small>{step.detail}</small>
            </span>
            <span className="ct">{step.note}</span>
          </div>
        ))}
      </div>

      <Notes
        notes={[
          { text: t('auth.aside.signIn.noteScope') },
          { text: t('auth.aside.signIn.noteSecrets'), color: 'var(--cat-teal)' },
          { text: t('auth.aside.signIn.noteApprovals'), color: 'var(--cat-amber)' },
        ]}
      />
    </>
  )
}

export function SignUpAside() {
  const { t } = useTranslation()
  return (
    <>
      <div className="auth-claim">
        <h2>{t('auth.aside.signUp.claim')}</h2>
        <p>{t('auth.aside.signUp.body')}</p>
      </div>

      <EvidenceList
        title={t('auth.aside.signUp.evidenceTitle')}
        hint={t('auth.aside.signUp.evidenceHint')}
        steps={[
          {
            title: t('auth.aside.signUp.owner'),
            detail: t('auth.aside.signUp.ownerDetail'),
            note: t('auth.aside.signUp.ownerNote'),
            tone: 'pri',
          },
          {
            title: t('auth.aside.signUp.empty'),
            detail: t('auth.aside.signUp.emptyDetail'),
            note: t('auth.aside.signUp.emptyNote'),
          },
          {
            title: t('auth.aside.signUp.policy'),
            detail: t('auth.aside.signUp.policyDetail'),
            note: t('auth.aside.signUp.policyNote'),
          },
          {
            title: t('auth.aside.signUp.audit'),
            detail: t('auth.aside.signUp.auditDetail'),
            note: t('auth.aside.signUp.auditNote'),
          },
        ]}
      />

      <Notes
        notes={[
          { text: t('auth.aside.signUp.noteAuth') },
          { text: t('auth.aside.signUp.noteReset'), color: 'var(--cat-amber)' },
        ]}
      />
    </>
  )
}

export function ResetAside() {
  const { t } = useTranslation()
  return (
    <>
      <div className="auth-claim">
        <h2>{t('auth.aside.reset.claim')}</h2>
        <p>{t('auth.aside.reset.body')}</p>
      </div>

      <Notes
        notes={[
          { text: t('auth.aside.reset.noteFields') },
          { text: t('auth.aside.reset.noteSecrets'), color: 'var(--cat-teal)' },
          { text: t('auth.aside.reset.noteTiles'), color: 'var(--cat-amber)' },
        ]}
      />
    </>
  )
}
