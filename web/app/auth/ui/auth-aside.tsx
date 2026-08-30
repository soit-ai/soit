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
  return (
    <>
      <div className="auth-claim">
        <h2>Every reply is a governed run.</h2>
        <p>
          Nothing an agent does here is off the record. A request becomes a run,
          the run is checked against the workspace&apos;s policy before it acts,
          and what it did is kept as evidence you can replay.
        </p>
      </div>

      <div className="panel auth-evidence">
        <div className="panel-head">
          <h2>What one run leaves behind</h2>
          <span className="hint">run detail</span>
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
          { title: 'Policy verdict', detail: '2/2 gates · egress allowlist', note: 'before it acted', tone: 'pri' as const },
          { title: 'Tool call', detail: 'helpdesk-api · tickets.write', note: 'arguments kept' },
          { title: 'Citations', detail: 'product-docs · 2 sources', note: 'quoted spans' },
          { title: 'Audit entry', detail: 'aud_8811 · retained', note: 'exportable' },
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
          { text: 'Your access is scoped to the workspaces you were granted.' },
          { text: 'Secrets are referenced, never shown back to an agent.', color: 'var(--cat-teal)' },
          { text: 'Actions above your role stop at an approval, not a failure.', color: 'var(--cat-amber)' },
        ]}
      />
    </>
  )
}

export function SignUpAside() {
  return (
    <>
      <div className="auth-claim">
        <h2>One workspace, one policy, one trail.</h2>
        <p>
          A new account comes with its own workspace. Agents, knowledge and
          secrets belong to it, and nothing crosses into another one — including
          the evidence a run leaves behind.
        </p>
      </div>

      <EvidenceList
        title="What you get on day one"
        hint="owner"
        steps={[
          { title: 'Owner role', detail: 'invite the rest of the team later', note: 'full access', tone: 'pri' },
          { title: 'An empty workspace', detail: 'no sample agents, no seeded data', note: 'yours' },
          { title: 'Policy on from the start', detail: 'egress allowlist · approval gates', note: 'before first run' },
          { title: 'Audit from the first call', detail: 'retained and exportable', note: 'day one' },
        ]}
      />

      <Notes
        notes={[
          { text: 'Community builds authenticate with email and password only.' },
          { text: 'Password reset is not available yet — keep your credentials safe.', color: 'var(--cat-amber)' },
        ]}
      />
    </>
  )
}

export function ResetAside() {
  return (
    <>
      <div className="auth-claim">
        <h2>We would rather say no than pretend.</h2>
        <p>
          A reset form that accepts your address and sends nothing is worse than
          no form at all: you wait for mail that will never arrive. The same
          rule holds inside the console — a figure with nothing behind it is
          left blank rather than filled with something plausible.
        </p>
      </div>

      <Notes
        notes={[
          { text: 'Sign-in never says which of the two fields was wrong.' },
          { text: 'Secrets are referenced, never shown back to an agent.', color: 'var(--cat-teal)' },
          { text: 'Tiles with no endpoint behind them read "not reported", not zero.', color: 'var(--cat-amber)' },
        ]}
      />
    </>
  )
}
