import { useEffect, useState } from 'react'
import { getDocument, type DocumentDetail, type Line } from '../api.ts'
import styles from './LinesPreview.module.css'

/** A heading is the line that gave its section its name (ignoring "#" and ":"). */
function isHeading(line: Line): boolean {
  return line.text.replace(/^[# ]+|:$/g, '') === line.section
}

/**
 * The document as FitGrid read it. These line numbers are what later results
 * cite, so the user should be able to see that the parsing is right.
 */
export function LinesPreview({ documentId }: { documentId: string }) {
  const [document, setDocument] = useState<DocumentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stale = false
    getDocument(documentId)
      .then((result) => !stale && setDocument(result))
      .catch((failure: Error) => !stale && setError(failure.message))
    return () => {
      stale = true
    }
  }, [documentId])

  if (error) return <p role="alert">{error}</p>
  if (!document) return <p>Loading…</p>

  return (
    <section aria-label="Parsed lines">
      <h2 className={styles.title}>{document.title}</h2>
      <p className={styles.hint}>
        This is what FitGrid read. Results will cite these line numbers, so check that they look
        right.
      </p>
      <ol className={styles.lines}>
        {document.lines.map((line) => (
          <li key={line.number} className={styles.line}>
            <span className={styles.number}>{line.number}</span>
            <span className={isHeading(line) ? styles.heading : ''}>{line.text}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
