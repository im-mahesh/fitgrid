import type { Verdict } from '../api.ts'
import styles from './VerdictBadge.module.css'
import { VERDICT_LABELS } from './verdicts.ts'

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={`${styles.badge} ${styles[verdict]}`}>{VERDICT_LABELS[verdict]}</span>
}
