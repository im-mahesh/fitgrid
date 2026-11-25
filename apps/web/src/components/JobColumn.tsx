import { useState } from 'react'
import { extractRequirements, runMatch, type JobOverview, type Requirement } from '../api.ts'
import styles from './FitGrid.module.css'
import { VerdictBadge } from './VerdictBadge.tsx'
import { summarize } from './verdicts.ts'

interface JobColumnProps {
  entry: JobOverview
  hasResume: boolean
  selected: number | null
  onSelect: (position: number) => void
  onChanged: () => Promise<unknown>
}

/** The one billed step this job still needs, if any. */
function nextStep({ requirements, matches }: JobOverview, hasResume: boolean) {
  if (!requirements) {
    return { label: 'Extract requirements', note: 'Sends the job post to Anthropic.', run: extractRequirements }
  }
  if (!matches && hasResume && requirements.length > 0) {
    return {
      label: 'Compare with my resume',
      note: 'Sends your resume (emails and phone numbers removed) to Anthropic.',
      run: runMatch,
    }
  }
  return null
}

export function JobColumn({ entry, hasResume, selected, onSelect, onChanged }: JobColumnProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { job, requirements, matches } = entry
  const step = nextStep(entry, hasResume)

  async function perform(run: (jobId: string) => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await run(job.id)
      await onChanged()
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // Must-haves first: they decide whether the job is worth applying for.
  const ordered = [...(requirements ?? [])].sort(
    (a, b) => Number(a.importance === 'nice') - Number(b.importance === 'nice'),
  )

  const cell = (requirement: Requirement) => {
    const verdict = matches?.find((m) => m.position === requirement.position)?.verdict
    return (
      <li key={requirement.position}>
        <button
          type="button"
          className={styles.cell}
          aria-pressed={selected === requirement.position}
          onClick={() => onSelect(requirement.position)}
        >
          {verdict && (
            <>
              <VerdictBadge verdict={verdict} />{' '}
            </>
          )}
          <span>{requirement.text}</span>
          {requirement.importance === 'nice' && <span className={styles.nice}> (nice to have)</span>}
        </button>
      </li>
    )
  }

  return (
    <article className={styles.column} aria-label={job.title}>
      <h3 className={styles.title}>{job.title}</h3>
      {requirements && matches && (
        <p className={styles.summary}>{summarize(requirements, matches)}</p>
      )}
      {step && (
        <>
          <button type="button" className={styles.action} onClick={() => perform(step.run)} disabled={busy}>
            {busy ? 'Working… up to a minute' : step.label}
          </button>
          <p className={styles.hint}>{step.note} Uses your API credit.</p>
        </>
      )}
      {requirements?.length === 0 && <p className={styles.hint}>No requirements found.</p>}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <ul className={styles.cells}>{ordered.map(cell)}</ul>
    </article>
  )
}
