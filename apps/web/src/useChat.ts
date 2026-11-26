import { useEffect, useRef, useState } from 'react'
import { streamChat, type ChatStreamEvent, type Source } from './api.ts'

export interface Turn {
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  stopped?: boolean
  error?: string
}

// The API's limits; it uses only the most recent turns anyway.
const MAX_HISTORY = 6
const MAX_CONTENT = 8000

function apply(turn: Turn, event: ChatStreamEvent): Turn {
  if (event.type === 'sources') return { ...turn, sources: event.sources }
  if (event.type === 'token') return { ...turn, content: turn.content + event.text }
  if (event.type === 'error') return { ...turn, error: event.message }
  return turn
}

/** The conversation lives here only: nothing is stored on the server. */
export function useChat(focusJobId: string | undefined) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => () => abort.current?.abort(), [])

  const updateAnswer = (change: (turn: Turn) => Turn) =>
    setTurns((current) => [...current.slice(0, -1), change(current[current.length - 1])])

  async function ask(question: string) {
    const history = turns
      .filter((turn) => turn.content.trim())
      .slice(-MAX_HISTORY)
      .map(({ role, content }) => ({ role, content: content.slice(0, MAX_CONTENT) }))
    const controller = new AbortController()
    abort.current = controller
    setBusy(true)
    setTurns((current) => [
      ...current,
      { role: 'user', content: question, sources: [] },
      { role: 'assistant', content: '', sources: [] },
    ])
    try {
      await streamChat(
        { question, history, focus_job_id: focusJobId ?? null },
        (event) => updateAnswer((turn) => apply(turn, event)),
        controller.signal,
      )
    } catch (failure) {
      updateAnswer((turn) =>
        controller.signal.aborted
          ? { ...turn, stopped: true }
          : { ...turn, error: (failure as Error).message },
      )
    } finally {
      setBusy(false)
    }
  }

  return { turns, busy, ask, stop: () => abort.current?.abort() }
}
