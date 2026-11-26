import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ChatStreamEvent, Source } from '../api.ts'
import { ChatPanel } from './ChatPanel.tsx'

const SOURCE: Source = { ref: 'R3', document_id: 'r1', line_number: 3, text: 'Built APIs' }
const SOURCES: ChatStreamEvent = { type: 'sources', jobs: [1], sources: [SOURCE] }
const token = (text: string): ChatStreamEvent => ({ type: 'token', text })
const DONE: ChatStreamEvent = { type: 'done' }

const sse = (events: ChatStreamEvent[]) =>
  events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')

/** Each reply is a body, a Response, or "hang": send one token and wait to be aborted. */
function fakeChat(...replies: (ChatStreamEvent[] | Response | 'hang')[]) {
  const bodies: Record<string, unknown>[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, init: RequestInit) => {
      bodies.push(JSON.parse(init.body as string))
      const reply = replies.shift() ?? [DONE]
      if (reply instanceof Response) return reply
      const stream = new ReadableStream({
        start(controller) {
          const send = (events: ChatStreamEvent[]) =>
            controller.enqueue(new TextEncoder().encode(sse(events)))
          if (reply !== 'hang') {
            send(reply)
            controller.close()
            return
          }
          send([SOURCES, token('Partial answer')])
          init.signal?.addEventListener('abort', () =>
            controller.error(new DOMException('Aborted', 'AbortError')),
          )
        },
      })
      return new Response(stream)
    }),
  )
  return bodies
}

function setup(props: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const onCite = vi.fn()
  render(<ChatPanel hasResume jobCount={2} onCite={onCite} {...props} />)
  return onCite
}

const input = () => screen.getByLabelText<HTMLTextAreaElement>('Your question')

function type(question: string) {
  fireEvent.change(input(), { target: { value: question } })
  fireEvent.keyDown(input(), { key: 'Enter' })
}

describe('ChatPanel', () => {
  it('asks a starter question and turns citations into buttons', async () => {
    const bodies = fakeChat([SOURCES, token('You built APIs '), token('[R3], not [R9].'), DONE])
    const onCite = setup()

    fireEvent.click(
      screen.getByRole('button', { name: 'How does my experience align with Job #2?' }),
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Resume line 3' }))
    expect(onCite).toHaveBeenCalledWith(SOURCE)
    expect(screen.getByRole('log').textContent).toContain('not [R9].')
    expect(bodies).toEqual([
      { question: 'How does my experience align with Job #2?', history: [], focus_job_id: null },
    ])
  })

  it('sends the open job and the earlier turns with a follow-up', async () => {
    const bodies = fakeChat([SOURCES, token('First answer'), DONE], [SOURCES, token('Two'), DONE])
    setup({ openJobId: 'j2' })

    type('What am I missing?')
    await screen.findByText('First answer')
    type('And how do I show it?')
    await screen.findByText('Two')

    expect(bodies[1]).toEqual({
      question: 'And how do I show it?',
      focus_job_id: 'j2',
      history: [
        { role: 'user', content: 'What am I missing?' },
        { role: 'assistant', content: 'First answer' },
      ],
    })
  })

  it('keeps the partial answer when stopped', async () => {
    fakeChat('hang')
    setup()

    type('Go on')
    await screen.findByText('Partial answer')
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

    expect(await screen.findByText('Stopped.')).toBeTruthy()
    expect(screen.getByText('Partial answer')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('button', { name: 'Send' })).toBeTruthy()
  })

  it.each([
    [
      'a refused request',
      new Response(JSON.stringify({ detail: 'Add your resume first.' }), { status: 409 }),
      'Add your resume first.',
    ],
    ['an error event', [{ type: 'error', message: 'The model declined.' }], 'The model declined.'],
    ['a stream that just stops', [token('half')], 'The answer was interrupted.'],
  ] as [string, ChatStreamEvent[] | Response, string][])('shows %s', async (_, reply, message) => {
    fakeChat(reply)
    setup()

    type('Hi')

    expect((await screen.findByRole('alert')).textContent).toBe(message)
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull())
  })

  it('does not send on Shift+Enter or when there is nothing to ask about', () => {
    const bodies = fakeChat()
    setup({ jobCount: 0 })

    expect(input().disabled).toBe(true)
    expect(screen.getByText(/Add your resume and at least one job/)).toBeTruthy()
    type('Hi')

    expect(bodies).toEqual([])
  })

  it('offers questions about "this role" when a job is open', () => {
    setup({ openJobId: 'j1' })

    expect(
      screen.getByRole('button', { name: 'What skills am I missing for this role?' }),
    ).toBeTruthy()
  })
})
