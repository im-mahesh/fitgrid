import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { JobOverview, Overview } from '../api.ts'
import { FitGrid } from './FitGrid.tsx'

function json(body: unknown, status = 200): Response {
  const headers = { 'content-type': 'application/json' }
  return new Response(JSON.stringify(body), { status, headers })
}

const summaryOf = (id: string, title: string) => ({
  id,
  kind: 'job' as const,
  title,
  filename: null,
  line_count: 2,
  created_at: '2026-01-01T00:00:00Z',
})

const requirement = (position: number, text: string, importance: 'must' | 'nice' = 'must') => ({
  position,
  text,
  importance,
  category: 'skill' as const,
  line_numbers: [2],
})

const COMPARED: JobOverview = {
  job: summaryOf('j1', 'Acme'),
  requirements: [requirement(1, 'Kafka', 'nice'), requirement(2, 'PostgreSQL')],
  matches: [
    { position: 1, verdict: 'not_found', reason: 'Kafka is not mentioned.', line_numbers: [] },
    { position: 2, verdict: 'met', reason: 'Your resume shows schema work.', line_numbers: [2] },
  ],
}
const NEW_JOB: JobOverview = { job: summaryOf('j2', 'Beta'), requirements: null, matches: null }
const READ_JOB: JobOverview = {
  job: summaryOf('j3', 'Gamma'),
  requirements: [requirement(1, 'Go')],
  matches: null,
}

function lines(id: string, texts: string[]) {
  return {
    ...summaryOf(id, id === 'r1' ? 'My resume' : 'Acme'),
    lines: texts.map((text, i) => ({ number: i + 1, section: null, text })),
  }
}

/** Fakes the API; returns the URLs of billed (POST) calls. */
function fakeApi(overview: Overview, post: () => Response = () => json({})) {
  const posts: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        posts.push(url)
        return post()
      }
      if (url === '/api/overview') return json(overview)
      if (url.endsWith('/r1')) return json(lines('r1', ['Jane', 'Designed PostgreSQL schemas']))
      return json(lines('j1', ['Platform Engineer', '- Strong PostgreSQL']))
    }),
  )
  return posts
}

const column = async (name: string) => within(await screen.findByRole('article', { name }))

describe('FitGrid', () => {
  it('shows one column per job, must-haves first, with counts and no score', async () => {
    fakeApi({ resume_id: 'r1', jobs: [COMPARED, NEW_JOB, READ_JOB] })
    render(<FitGrid />)

    const acme = await column('Acme')
    const cells = acme.getAllByRole('listitem').map((item) => item.textContent)
    expect(cells).toEqual(['Met PostgreSQL', 'Not found Kafka (nice to have)'])
    expect(acme.getByText('Must-haves (1): 1 met · 0 partial · 0 not found')).toBeTruthy()
    expect(document.body.textContent).not.toContain('%')
  })

  it('offers each job only the step it still needs, and calls nothing by itself', async () => {
    const posts = fakeApi({ resume_id: 'r1', jobs: [COMPARED, NEW_JOB, READ_JOB] })
    render(<FitGrid />)

    expect((await column('Acme')).queryByRole('button', { name: /Extract|Compare/ })).toBeNull()
    expect((await column('Beta')).getByRole('button', { name: 'Extract requirements' })).toBeTruthy()
    const gamma = await column('Gamma')
    expect(gamma.getByRole('button', { name: 'Compare with my resume' })).toBeTruthy()
    expect(posts).toEqual([])

    fireEvent.click(gamma.getByRole('button', { name: 'Compare with my resume' }))
    await vi.waitFor(() => expect(posts).toEqual(['/api/jobs/j3/match']))
  })

  it('shows a failure in the column it happened in', async () => {
    const failure = () => json({ detail: "Anthropic's rate limit was reached." }, 429)
    fakeApi({ resume_id: 'r1', jobs: [NEW_JOB] }, failure)
    render(<FitGrid />)

    const beta = await column('Beta')
    fireEvent.click(beta.getByRole('button', { name: 'Extract requirements' }))

    expect((await beta.findByRole('alert')).textContent).toContain('rate limit')
  })

  it('does not offer to compare without a resume', async () => {
    fakeApi({ resume_id: null, jobs: [READ_JOB] })
    render(<FitGrid />)

    expect(await screen.findByText(/Add your resume to compare/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Compare with my resume' })).toBeNull()
  })

  it('opens the evidence for a cell and closes it with Escape', async () => {
    fakeApi({ resume_id: 'r1', jobs: [COMPARED] })
    render(<FitGrid />)

    fireEvent.click(await screen.findByRole('button', { name: /^Met PostgreSQL/ }))
    const drawer = within(screen.getByRole('complementary', { name: 'Evidence' }))

    expect(drawer.getByText(/Your resume shows schema work/)).toBeTruthy()
    expect(await drawer.findByText('- Strong PostgreSQL')).toBeTruthy()
    const cited = await drawer.findByText('Designed PostgreSQL schemas')
    expect(cited.closest('li')?.getAttribute('aria-current')).toBe('true')

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('complementary', { name: 'Evidence' })).toBeNull()
  })

  it('says when no resume line supports a requirement', async () => {
    fakeApi({ resume_id: 'r1', jobs: [COMPARED] })
    render(<FitGrid />)

    fireEvent.click(await screen.findByRole('button', { name: /^Not found Kafka/ }))

    expect(screen.getByText('No resume line supports this requirement.')).toBeTruthy()
  })
})
