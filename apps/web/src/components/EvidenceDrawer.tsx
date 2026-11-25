import { useEffect, useState } from 'react'
import { getDocument, type DocumentDetail, type JobOverview } from '../api.ts'
import styles from './EvidenceDrawer.module.css'
import { LinesPreview } from './LinesPreview.tsx'
import { VerdictBadge } from './VerdictBadge.tsx'

interface EvidenceDrawerProps {
  entry: JobOverview
  position: number
  resumeId: string | null
  onClose: () => void
}

/** Why a cell says what it says: the reason, the job lines and the resume lines. */
export function EvidenceDrawer({ entry, position, resumeId, onClose }: EvidenceDrawerProps) {
  const [job, setJob] = useState<DocumentDetail | null>(null)
  const requirement = entry.requirements?.find((r) => r.position === position)
  const match = entry.matches?.find((m) => m.position === position)

  useEffect(() => {
    getDocument(entry.job.id)
      .then(setJob)
      .catch(() => setJob(null)) // the drawer still shows the reason and resume lines
  }, [entry.job.id])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  if (!requirement) return null
  const jobLines = job?.lines.filter((line) => requirement.line_numbers.includes(line.number)) ?? []

  return (
    <aside className={styles.drawer} aria-label="Evidence">
      <button type="button" className={styles.close} onClick={onClose} aria-label="Close evidence">
        ×
      </button>
      <h2 className={styles.title}>{requirement.text}</h2>
      <p className={styles.where}>{entry.job.title}</p>

      {match ? (
        <p>
          <VerdictBadge verdict={match.verdict} /> {match.reason}
        </p>
      ) : (
        <p className={styles.where}>Not compared with your resume yet.</p>
      )}

      <h3 className={styles.heading}>The job post says</h3>
      <ul className={styles.quotes}>
        {jobLines.map((line) => (
          <li key={line.number}>
            <span className={styles.number}>{line.number}</span> {line.text}
          </li>
        ))}
      </ul>

      {match && resumeId && match.line_numbers.length > 0 && (
        <LinesPreview
          documentId={resumeId}
          highlighted={match.line_numbers}
          hint="The highlighted lines were cited for this verdict. Read them in context."
        />
      )}
      {match && match.line_numbers.length === 0 && (
        <p className={styles.where}>No resume line supports this requirement.</p>
      )}
    </aside>
  )
}
