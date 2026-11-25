import type { DocumentSummary } from '../api.ts'
import styles from './DocumentCard.module.css'

interface DocumentCardProps {
  document: DocumentSummary
  selected: boolean
  onSelect: () => void
  onRemove: () => void
}

export function DocumentCard({ document, selected, onSelect, onRemove }: DocumentCardProps) {
  return (
    <div className={`${styles.card} ${selected ? styles.selected : ''}`}>
      <button type="button" className={styles.open} onClick={onSelect} aria-pressed={selected}>
        <span className={styles.title}>{document.title}</span>
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
