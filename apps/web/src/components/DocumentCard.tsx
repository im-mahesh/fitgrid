import type { DocumentSummary } from '../api.ts'
import styles from './DocumentCard.module.css'

interface DocumentCardProps {
  document: DocumentSummary
  number?: number // jobs only: what "Job #2" refers to in the chat
  selected: boolean
  onSelect: () => void
  onRemove: () => void
}

export function DocumentCard({ document, number, selected, onSelect, onRemove }: DocumentCardProps) {
  return (
    <div className={`${styles.card} ${selected ? styles.selected : ''}`}>
      <button type="button" className={styles.open} onClick={onSelect} aria-pressed={selected}>
        <span className={styles.title}>
          {number !== undefined && <span className={styles.number}>#{number}</span>}{' '}
          {document.title}
        </span>
        <span className={styles.meta}>
          {document.line_count} {document.line_count === 1 ? 'line' : 'lines'}
        </span>
      </button>
      <button
        type="button"
        className={styles.remove}
        onClick={onRemove}
        aria-label={`Remove ${document.title}`}
      >
        ×
      </button>
    </div>
  )
}
