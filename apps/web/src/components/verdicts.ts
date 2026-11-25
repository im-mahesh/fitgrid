import type { Match, Requirement, Verdict } from '../api.ts'

export const VERDICT_LABELS: Record<Verdict, string> = {
  met: 'Met',
  partial: 'Partial',
  not_found: 'Not found',
  not_assessed: 'Not assessed',
}

/** "2 met · 1 partial · 0 not found" for the must-haves. Counts, never a score. */
export function summarize(requirements: Requirement[], matches: Match[]): string {
  const must = new Set(requirements.filter((r) => r.importance === 'must').map((r) => r.position))
  const relevant = matches.filter((m) => must.has(m.position))
  const count = (verdict: Verdict) => relevant.filter((m) => m.verdict === verdict).length
  const parts = (['met', 'partial', 'not_found'] as const).map(
    (verdict) => `${count(verdict)} ${VERDICT_LABELS[verdict].toLowerCase()}`,
  )
  if (count('not_assessed') > 0) parts.push(`${count('not_assessed')} not assessed`)
  return `Must-haves (${must.size}): ${parts.join(' · ')}`
}
