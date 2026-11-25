import type { Match, MatchResponse, Requirement } from '../api.ts'
import styles from './JobView.module.css'
import { summarize } from './verdicts.ts'

interface MatchBarProps {
  requirements: Requirement[]
  hasResume: boolean
  data: MatchResponse | null
  busy: boolean
  error: string | null
  onCompare: () => void
}

/** Offers the comparison, then summarizes it. */
export function MatchBar({ requirements, hasResume, data, busy, error, onCompare }: MatchBarProps) {
  if (!hasResume) {
    return <p className={styles.hint}>Add your resume to compare it with these requirements.</p>
  }
  const results: Match[] = data?.results ?? []
  return (
    <div className={styles.match}>
      {data?.matched && (
        <>
          <p className={styles.summary}>{summarize(requirements, results)}</p>
          <p className={styles.hint}>
            Judged by {data.model}. &quot;Not found&quot; means your resume doesn&apos;t show it,
            not that you lack it. Check the cited lines before relying on a verdict.
          </p>
        </>
      )}
      {data && !data.matched && (
        <>
          <p className={styles.hint}>
            This sends your whole resume (emails and phone numbers removed) and these requirements
            to Anthropic, and uses your API credit. The result is saved.
          </p>
          <button type="button" className={styles.extract} onClick={onCompare} disabled={busy}>
            {busy ? 'Comparing… this can take a minute' : 'Compare with my resume'}
          </button>
        </>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
