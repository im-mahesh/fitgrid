import type { Match, Requirement } from '../api.ts'
import styles from './RequirementRow.module.css'
import { VerdictBadge } from './VerdictBadge.tsx'

interface RequirementRowProps {
  requirement: Requirement
  match?: Match
  selected: boolean
  onSelect: () => void
}

const lines = (numbers: number[]) =>
  `line${numbers.length > 1 ? 's' : ''} ${numbers.join(', ')}`

export function RequirementRow({ requirement, match, selected, onSelect }: RequirementRowProps) {
  return (
    <li>
      <button type="button" className={styles.item} aria-pressed={selected} onClick={onSelect}>
        {match && (
          <>
            <VerdictBadge verdict={match.verdict} />{' '}
          </>
        )}
        <span className={styles.text}>{requirement.text}</span>{' '}
        <span className={styles.meta}>
          {requirement.category} · job {lines(requirement.line_numbers)}
        </span>
      </button>
      {selected && match && (
        <p className={styles.reason}>
          {match.reason}
          {match.line_numbers.length > 0 && ` (Resume ${lines(match.line_numbers)}.)`}
        </p>
      )}
    </li>
  )
}
