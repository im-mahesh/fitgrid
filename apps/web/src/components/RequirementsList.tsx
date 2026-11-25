import type { Match, Requirement } from '../api.ts'
import { RequirementRow } from './RequirementRow.tsx'
import styles from './JobView.module.css'

interface RequirementsListProps {
  requirements: Requirement[]
  matches: Match[]
  selected: number | null
  onSelect: (position: number) => void
}

const GROUPS = [
  { importance: 'must', title: 'Must have' },
  { importance: 'nice', title: 'Nice to have' },
] as const

/** Requirements grouped by importance, each with its verdict once compared. */
export function RequirementsList(props: RequirementsListProps) {
  const { requirements, matches, selected, onSelect } = props
  return (
    <>
      {GROUPS.map(({ importance, title }) => {
        const items = requirements.filter((r) => r.importance === importance)
        if (items.length === 0) return null
        return (
          <div key={importance}>
            <h3 className={styles.group}>
              {title} ({items.length})
            </h3>
            <ul className={styles.list}>
              {items.map((requirement) => (
                <RequirementRow
                  key={requirement.position}
                  requirement={requirement}
                  match={matches.find((m) => m.position === requirement.position)}
                  selected={selected === requirement.position}
                  onSelect={() => onSelect(requirement.position)}
                />
              ))}
            </ul>
          </div>
        )
      })}
    </>
  )
}
