import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { Source } from '../api.ts'
import { useChat, type Turn } from '../useChat.ts'
import { ChatAnswer } from './ChatAnswer.tsx'
import styles from './ChatPanel.module.css'

const MAX_QUESTION = 2000
const NEAR_BOTTOM_PX = 80

interface ChatPanelProps {
  hasResume: boolean
  jobCount: number
  openJobId?: string
  onCite: (source: Source) => void
}

function starters(jobCount: number, jobOpen: boolean): string[] {
  if (jobOpen) {
    return [
      'What skills am I missing for this role?',
      'How does my experience align with this role?',
      'Help me prepare for an interview for this role.',
    ]
  }
  return [
    'What skills am I missing for Job #1?',
    `How does my experience align with Job #${Math.min(jobCount, 2)}?`,
    jobCount > 1 ? 'Which job fits my resume best?' : 'Help me prepare for an interview.',
  ]
}

export function ChatPanel({ hasResume, jobCount, openJobId, onCite }: ChatPanelProps) {
  const { turns, busy, ask, stop } = useChat(openJobId)
  const [draft, setDraft] = useState('')
  const log = useRef<HTMLDivElement>(null)
  const follow = useRef(true) // false once the reader scrolls up
  const ready = hasResume && jobCount > 0

  useEffect(() => {
    if (follow.current && log.current) log.current.scrollTop = log.current.scrollHeight
  }, [turns])

  function send(question: string) {
    if (!ready || busy || !question.trim()) return
    follow.current = true
    setDraft('')
    void ask(question.trim())
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    send(draft)
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      send(draft)
    }
  }

  function onScroll() {
    const box = log.current
    if (box) follow.current = box.scrollHeight - box.scrollTop - box.clientHeight < NEAR_BOTTOM_PX
  }

  const answer = (turn: Turn, streaming: boolean) => (
    <>
      {turn.content && (
        <ChatAnswer content={turn.content} sources={turn.sources} onCite={onCite} />
      )}
      {streaming && !turn.content && <p className={styles.note}>Reading your documents…</p>}
      {turn.stopped && <p className={styles.note}>Stopped.</p>}
      {turn.error && (
        <p className={styles.error} role="alert">
          {turn.error}
        </p>
      )}
    </>
  )

  return (
    <section aria-label="Chat" className={styles.panel}>
      <h2 className={styles.title}>Ask about your fit</h2>

      <div className={styles.log} ref={log} onScroll={onScroll} role="log" aria-live="off">
        {turns.map((turn, index) =>
          turn.role === 'user' ? (
            <p key={index} className={styles.question}>
              {turn.content}
            </p>
          ) : (
            <div key={index}>{answer(turn, busy && index === turns.length - 1)}</div>
          ),
        )}
        {turns.length === 0 && !ready && (
          <p className={styles.note}>Add your resume and at least one job to start asking.</p>
        )}
        {turns.length === 0 && ready && (
          <ul className={styles.starters} aria-label="Example questions">
            {starters(jobCount, openJobId !== undefined).map((question) => (
              <li key={question}>
                <button type="button" className={styles.starter} onClick={() => send(question)}>
                  {question}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <form onSubmit={onSubmit} className={styles.form}>
        <textarea
          className={styles.input}
          aria-label="Your question"
          placeholder="Ask about gaps, fit or interview prep"
          rows={2}
          maxLength={MAX_QUESTION}
          value={draft}
          disabled={!ready}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
        />
        {busy ? (
          <button type="button" className={styles.send} onClick={stop}>
            Stop
          </button>
        ) : (
          <button type="submit" className={styles.send} disabled={!ready || !draft.trim()}>
            Send
          </button>
        )}
      </form>
      <p className={styles.note}>
        Each question sends relevant resume lines (emails and phone numbers removed) and job lines
        to Anthropic and uses your API credit. The conversation isn&apos;t saved.
      </p>
    </section>
  )
}
