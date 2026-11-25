import { useState } from 'react'
import { extractRequirements, getMatch, getRequirements, runMatch } from '../api.ts'
import { useStoredResult } from '../useStoredResult.ts'
import { LinesPreview } from './LinesPreview.tsx'
import { MatchBar } from './MatchBar.tsx'
import { RequirementsList } from './RequirementsList.tsx'
import styles from './JobView.module.css'

type Source = 'job' | 'resume'

/**
 * A job's requirements and verdicts above the evidence. Choosing a requirement
 * shows the resume lines behind its verdict, or the job lines it came from.
 */
export function JobView({ jobId, resumeId }: { jobId: string; resumeId?: string }) {
  const extraction = useStoredResult(jobId, getRequirements, extractRequirements)
  const requirements = extraction.data?.requirements ?? []
  const comparison = useStoredResult(jobId, getMatch, runMatch, requirements.length > 0)
  const matches = comparison.data?.results ?? []
  const [selected, setSelected] = useState<number | null>(null)
  const [source, setSource] = useState<Source>('job')

  const requirement = requirements.find((r) => r.position === selected)
  const match = matches.find((m) => m.position === selected)
  const showResume = source === 'resume' && resumeId !== undefined
  const highlighted = showResume ? match?.line_numbers : requirement?.line_numbers

  function select(position: number) {
    setSelected(position)
    const evidence = matches.find((m) => m.position === position)?.line_numbers.length
    setSource(evidence ? 'resume' : 'job')
  }

  const tab = (value: Source, label: string) => (
    <button
      type="button"
      className={styles.tab}
      aria-pressed={source === value}
      onClick={() => setSource(value)}
    >
      {label}
    </button>
  )

  return (
    <>
      <section aria-label="Requirements" className={styles.panel}>
        <h2 className={styles.title}>Requirements</h2>
        {extraction.data && !extraction.data.extracted && (
          <>
            <p className={styles.hint}>
              This sends the job post to Anthropic and uses your API credit. The result is saved.
            </p>
            <button
              type="button"
              className={styles.extract}
              onClick={extraction.run}
              disabled={extraction.busy}
            >
              {extraction.busy ? 'Reading the job post…' : 'Extract requirements'}
            </button>
          </>
        )}
        {extraction.data?.extracted && requirements.length === 0 && (
          <p className={styles.hint}>No requirements were found in this post.</p>
        )}
        {requirements.length > 0 && (
          <>
            <MatchBar
              requirements={requirements}
              hasResume={resumeId !== undefined}
              data={comparison.data}
              busy={comparison.busy}
              error={comparison.error}
              onCompare={comparison.run}
            />
            <RequirementsList
              requirements={requirements}
              matches={matches}
              selected={selected}
              onSelect={select}
            />
            <p className={styles.hint}>
              Requirements extracted by {extraction.data?.model}. It can miss or misread some, so
              check them against the post.
            </p>
          </>
        )}
        {extraction.error && (
          <p className={styles.error} role="alert">
            {extraction.error}
          </p>
        )}
      </section>

      {resumeId && matches.length > 0 && (
        <div className={styles.tabs} role="group" aria-label="Evidence from">
          {tab('job', 'Job post')}
          {tab('resume', 'Your resume')}
        </div>
      )}
      {showResume ? (
        <LinesPreview key={resumeId} documentId={resumeId} highlighted={highlighted} />
      ) : (
        <LinesPreview key={jobId} documentId={jobId} highlighted={highlighted} />
      )}
    </>
  )
}
