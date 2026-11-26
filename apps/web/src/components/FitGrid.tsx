import { useCallback, useEffect, useState } from 'react'
import { getOverview, type Overview } from '../api.ts'
import { EvidenceDrawer } from './EvidenceDrawer.tsx'
import styles from './FitGrid.module.css'
import { JobColumn } from './JobColumn.tsx'

interface Cell {
  jobId: string
  position: number
}

/** Every job side by side: each requirement and whether the resume shows it. */
export function FitGrid() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cell, setCell] = useState<Cell | null>(null)

  const reload = useCallback(
    () =>
      getOverview()
        .then(setOverview)
        .catch((failure: Error) => setError(failure.message)),
    [],
  )

  useEffect(() => {
    getOverview()
      .then(setOverview)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  if (error) return <p role="alert">{error}</p>
  if (!overview) return <p>Loading…</p>
  if (overview.jobs.length === 0) {
    return <p className={styles.hint}>Add your resume and up to five jobs to fill the grid.</p>
  }

  const open = overview.jobs.find((entry) => entry.job.id === cell?.jobId)

  return (
    <section aria-label="Fit grid">
      <p className={styles.hint}>
        {overview.resume_id
          ? 'Choose a requirement to see the evidence. "Not found" means your resume doesn’t show it.'
          : 'Add your resume to compare it with these jobs.'}
      </p>
      <div className={styles.grid}>
        {overview.jobs.map((entry, index) => (
          <JobColumn
            key={entry.job.id}
            number={index + 1}
            entry={entry}
            hasResume={overview.resume_id !== null}
            selected={cell?.jobId === entry.job.id ? cell.position : null}
            onSelect={(position) => setCell({ jobId: entry.job.id, position })}
            onChanged={reload}
          />
        ))}
      </div>
      {open && cell && (
        <EvidenceDrawer
          key={`${cell.jobId}:${cell.position}`}
          entry={open}
          position={cell.position}
          resumeId={overview.resume_id}
          onClose={() => setCell(null)}
        />
      )}
    </section>
  )
}
