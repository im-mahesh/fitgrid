import type { Source } from '../api.ts'
import { parseCitations, sourceLabel } from '../citations.ts'
import styles from './ChatPanel.module.css'

/** Plain text, with the model's [R3] and [J2:5] markers as buttons that show the line. */
export function ChatAnswer({
  content,
  sources,
  onCite,
}: {
  content: string
  sources: Source[]
  onCite: (source: Source) => void
}) {
  return (
    <p className={styles.text}>
      {parseCitations(content, sources).map((segment, index) =>
        'text' in segment ? (
          <span key={index}>{segment.text}</span>
        ) : (
          <button
            key={index}
            type="button"
            className={styles.citation}
            aria-label={sourceLabel(segment.source)}
            title={segment.source.text}
            onClick={() => onCite(segment.source)}
          >
            {segment.source.ref}
          </button>
        ),
      )}
    </p>
  )
}
