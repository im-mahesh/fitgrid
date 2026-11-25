import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Requirement } from '../api.ts'
import { JobView } from './JobView.tsx'

const LINES = [
  { number: 1, section: null, text: 'Platform Engineer' },
  { number: 2, section: null, text: '- Python or Go' },
  { number: 3, section: null, text: '- Kubernetes is a plus' },
]

const REQUIREMENTS: Requirement[] = [
  { position: 1, text: 'Python or Go', importance: 'must', category: 'skill', line_numbers: [2] },
  { position: 2, text: 'Kubernetes', importance: 'nice', category: 'skill', line_numbers: [3] },
]

function json(body: unknown, status = 200): Response {
  const headers = { 'content-type': 'application/json' }
  return new Response(JSON.stringify(body), { status, headers })
}

function fakeApi(post: () => Response, stored: Requirement[] | null = null) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (!url.endsWith('/requirements')) {
      return json({ id: 'j1', kind: 'job', title: 'Job', line_count: 3, lines: LINES })
    }
    if (init?.method === 'POST') return post()
    return json({ extracted: stored !== null, model: null, requirements: stored ?? [] })
  })
  vi.stubGlobal('fetch', fetch)
  return () => fetch.mock.calls.filter(([, init]) => init?.method === 'POST').length
}

const extracted = () =>
  json({ extracted: true, model: 'claude-opus-5-5', requirements: REQUIREMENTS })

describe('JobView', () => {
  it('calls the model only when the button is pressed, then groups the requirements', async () => {
    const posts = fakeApi(extracted)
    render(<JobView jobId="j1" />)

    const button = await screen.findByRole('button', { name: 'Extract requirements' })
    expect(posts()).toBe(0)
    fireEvent.click(button)

    expect(await screen.findByText('Must have (1)')).toBeTruthy()
    expect(screen.getByText('Nice to have (1)')).toBeTruthy()
    expect(posts()).toBe(1)
  })

  it('highlights the cited line of the job post when a requirement is chosen', async () => {
    fakeApi(extracted, REQUIREMENTS)
    render(<JobView jobId="j1" />)
    const post = await screen.findByRole('region', { name: 'Parsed lines' })

    fireEvent.click(await screen.findByRole('button', { name: /Kubernetes skill/ }))

    const current = within(post)
      .getAllByRole('listitem')
      .filter((item) => item.getAttribute('aria-current') === 'true')
    expect(current.map((item) => item.textContent)).toEqual(['3- Kubernetes is a plus'])
  })

  it('shows why extraction failed and lets the user try again', async () => {
    fakeApi(() => json({ detail: 'ANTHROPIC_API_KEY is not set.' }, 503))
    render(<JobView jobId="j1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Extract requirements' }))

    expect((await screen.findByRole('alert')).textContent).toContain('ANTHROPIC_API_KEY')
    const retry = screen.getByRole('button', { name: 'Extract requirements' })
    expect(retry.hasAttribute('disabled')).toBe(false)
  })

  it('says so when a post has no requirements', async () => {
    fakeApi(extracted, [])
    render(<JobView jobId="j1" />)

    expect(await screen.findByText('No requirements were found in this post.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Extract requirements' })).toBeNull()
  })
})
