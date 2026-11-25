import { useEffect, useRef, useState } from 'react'
import { getDocument, type DocumentDetail, type Line } from '../api.ts'
import styles from './LinesPreview.module.css'

/** A heading is the line that gave its section its name (ignoring "#" and ":"). */
function isHeading(line: Line): boolean {
  return line.text.replace(/^[# ]+|:$/g, '') === line.section
}

const PARSING_HINT =
  'This is what FitGrid read. Results will cite these line numbers, so check that they look right.'

/**
 * The document as FitGrid read it. These line numbers are what later results
 * cite, so the user should be able to see that the parsing is right.
 */
export function LinesPreview({
  documentId,
  highlighted = [],
  hint = PARSING_HINT,
}: {
  documentId: string
  highlighted?: number[]
  hint?: string
}) {
  const firstHighlighted = useRef<HTMLLIElement>(null)
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

  useEffect(() => {
    firstHighlighted.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
  }, [highlighted])

  if (error) return <p role="alert">{error}</p>
  if (!document) return <p>Loading…</p>

  return (
    <section aria-label="Parsed lines">
      <h2 className={styles.title}>{document.title}</h2>
      <p className={styles.hint}>{hint}</p>
      <ol className={styles.lines}>
        {document.lines.map((line) => (
          <li
            key={line.number}
            ref={line.number === highlighted[0] ? firstHighlighted : undefined}
            className={`${styles.line} ${highlighted.includes(line.number) ? styles.highlight : ''}`}
            aria-current={highlighted.includes(line.number) ? 'true' : undefined}
          >
            <span className={styles.number}>{line.number}</span>
            <span className={isHeading(line) ? styles.heading : ''}>{line.text}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
