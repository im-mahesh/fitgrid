import { useEffect, useState } from 'react'
import {
  extractRequirements,
  getRequirements,
  type Requirement,
  type RequirementsResponse,
} from '../api.ts'
import styles from './RequirementsPanel.module.css'

interface RequirementsPanelProps {
  jobId: string
  highlighted: number[]
  onShowLines: (lines: number[]) => void
}

const GROUPS = [
  { importance: 'must', title: 'Must have' },
  { importance: 'nice', title: 'Nice to have' },
] as const

export function RequirementsPanel({ jobId, highlighted, onShowLines }: RequirementsPanelProps) {
  const [data, setData] = useState<RequirementsResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stale = false
    getRequirements(jobId)
      .then((result) => !stale && setData(result))
      .catch((failure: Error) => !stale && setError(failure.message))
    return () => {
      stale = true
    }
  }, [jobId])

  async function extract() {
    setBusy(true)
    setError(null)
    try {
      setData(await extractRequirements(jobId))
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const row = (requirement: Requirement) => (
    <li key={requirement.position}>
      <button
        type="button"
        className={styles.item}
        aria-pressed={requirement.line_numbers.join() === highlighted.join()}
        onClick={() => onShowLines(requirement.line_numbers)}
      >
        <span>{requirement.text}</span>{' '}
        <span className={styles.meta}>
          {requirement.category} · line {requirement.line_numbers.join(', ')}
        </span>
      </button>
    </li>
  )

  return (
    <section aria-label="Requirements" className={styles.panel}>
      <h2 className={styles.title}>Requirements</h2>
      {data && !data.extracted && (
        <>
          <p className={styles.hint}>
            This sends the job post to Anthropic and uses your API credit. The result is saved.
          </p>
          <button type="button" className={styles.extract} onClick={extract} disabled={busy}>
            {busy ? 'Reading the job post…' : 'Extract requirements'}
          </button>
        </>
      )}
      {data?.extracted && data.requirements.length === 0 && (
        <p className={styles.hint}>No requirements were found in this post.</p>
      )}
      {data?.extracted &&
        GROUPS.map(({ importance, title }) => {
          const items = data.requirements.filter((r) => r.importance === importance)
          if (items.length === 0) return null
          return (
            <div key={importance}>
              <h3 className={styles.group}>
                {title} ({items.length})
              </h3>
              <ul className={styles.list}>{items.map(row)}</ul>
            </div>
          )
        })}
      {data?.extracted && (
        <p className={styles.hint}>
          Extracted by {data.model}. It can miss or misread requirements, so check them against the
          post.
        </p>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
