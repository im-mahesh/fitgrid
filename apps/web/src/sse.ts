/**
 * Split a server-sent-events buffer into the complete `data:` payloads and the
 * unfinished tail, which the caller keeps and prepends to the next chunk.
 */
export function splitEvents(buffer: string): { data: string[]; rest: string } {
  const blocks = buffer.split(/\r?\n\r?\n/)
  const rest = blocks.pop() ?? ''
  const data = blocks.flatMap((block) => {
    const lines = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
    return lines.length ? [lines.join('\n')] : []
  })
  return { data, rest }
}
