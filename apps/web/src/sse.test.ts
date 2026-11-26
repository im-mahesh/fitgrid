import { describe, expect, it } from 'vitest'
import { splitEvents } from './sse.ts'

const STREAM = 'data: {"a":1}\n\ndata: {"b":"x\\n\\ny"}\r\n\r\n: keep-alive\n\ndata:{"c":3}\n\n'
const EXPECTED = ['{"a":1}', '{"b":"x\\n\\ny"}', '{"c":3}']

function readInPieces(pieces: string[]): string[] {
  let buffer = ''
  return pieces.flatMap((piece) => {
    const { data, rest } = splitEvents(buffer + piece)
    buffer = rest
    return data
  })
}

describe('splitEvents', () => {
  it('gives the same events wherever the stream is cut', () => {
    for (let cut = 0; cut <= STREAM.length; cut++) {
      expect(readInPieces([STREAM.slice(0, cut), STREAM.slice(cut)])).toEqual(EXPECTED)
    }
  })

  it('works one character at a time', () => {
    expect(readInPieces([...STREAM])).toEqual(EXPECTED)
  })

  it('keeps an unfinished event for later', () => {
    expect(splitEvents('data: 1\n\ndata: 2')).toEqual({ data: ['1'], rest: 'data: 2' })
  })
})
