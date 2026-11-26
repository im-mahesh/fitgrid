import type { Source } from './api.ts'

export type Segment = { text: string } | { source: Source }

// "[R3]", "[J2:5]" or a group such as "[R3, J2:5]"
const CITATION = /\[((?:R\d+|J\d+:\d+)(?:\s*[,;]\s*(?:R\d+|J\d+:\d+))*)\]/g

/**
 * Cut an answer into plain text and citations. Only refs the API sent as
 * sources become citations; anything else stays as the model wrote it.
 */
export function parseCitations(answer: string, sources: Source[]): Segment[] {
  const byRef = new Map(sources.map((source) => [source.ref, source]))
  const segments: Segment[] = []
  let done = 0
  for (const match of answer.matchAll(CITATION)) {
    const found = match[1].split(/\s*[,;]\s*/).map((ref) => byRef.get(ref))
    if (!found.every((source) => source !== undefined)) continue
    segments.push({ text: answer.slice(done, match.index) })
    segments.push(...found.map((source) => ({ source })))
    done = match.index + match[0].length
  }
  segments.push({ text: answer.slice(done) })
  return segments.filter((segment) => !('text' in segment) || segment.text !== '')
}

export function sourceLabel({ ref, line_number }: Source): string {
  const job = ref.match(/^J(\d+):/)
  return job ? `Job #${job[1]}, line ${line_number}` : `Resume line ${line_number}`
}
