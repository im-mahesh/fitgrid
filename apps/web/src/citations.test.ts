import { describe, expect, it } from 'vitest'
import type { Source } from './api.ts'
import { parseCitations, sourceLabel } from './citations.ts'

const source = (ref: string, line: number): Source => ({
  ref,
  document_id: 'd',
  line_number: line,
  text: ref,
})
const R3 = source('R3', 3)
const J = source('J2:5', 5)

describe('parseCitations', () => {
  it('turns known refs, single or grouped, into citations', () => {
    expect(parseCitations('Python [R3] is asked [R3, J2:5].', [R3, J])).toEqual([
      { text: 'Python ' },
      { source: R3 },
      { text: ' is asked ' },
      { source: R3 },
      { source: J },
      { text: '.' },
    ])
  })

  it('leaves refs that were never shown to the model as text', () => {
    const answer = 'Led teams [R99] and [R3, R99] [1]'

    expect(parseCitations(answer, [R3])).toEqual([{ text: answer }])
  })

  it('says which document a source is from', () => {
    expect(sourceLabel(R3)).toBe('Resume line 3')
    expect(sourceLabel(J)).toBe('Job #2, line 5')
  })
})
