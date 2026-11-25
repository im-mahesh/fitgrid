import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Match, Requirement } from '../api.ts'
import { JobView } from './JobView.tsx'

const JOB_LINES = ['Platform Engineer', '- Python or Go', '- Kubernetes is a plus']
const RESUME_LINES = ['Jane Doe', 'Built APIs in Python', 'Ran Docker']

const REQUIREMENTS: Requirement[] = [
  { position: 1, text: 'Python or Go', importance: 'must', category: 'skill', line_numbers: [2] },
  { position: 2, text: 'Kubernetes', importance: 'nice', category: 'skill', line_numbers: [3] },
]

const MATCHES: Match[] = [
  { position: 1, verdict: 'met', reason: 'Your resume shows Python APIs.', line_numbers: [2] },
  { position: 2, verdict: 'not_found', reason: 'No Kubernetes is shown.', line_numbers: [] },
]

function json(body: unknown, status = 200): Response {
  const headers = { 'content-type': 'application/json' }
  return new Response(JSON.stringify(body), { status, headers })
}

const document = (id: string, kind: 'job' | 'resume', texts: string[]) => ({
  id,
  kind,
  title: kind === 'job' ? 'The job' : 'My resume',
  line_count: texts.length,
  lines: texts.map((text, i) => ({ number: i + 1, section: null, text })),
})

interface Fake {
  requirements?: Requirement[] | null
  matches?: Match[] | null
  extract?: () => Response
  compare?: () => Response
}

const extracted = (requirements = REQUIREMENTS) =>
  json({ extracted: true, model: 'claude-opus-5-5', requirements })
const matched = () => json({ matched: true, model: 'claude-opus-5-5', results: MATCHES })

/** Fakes the API and returns a counter of billed (POST) calls per endpoint. */
function fakeApi({ requirements = REQUIREMENTS, matches = null, extract, compare }: Fake = {}) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const post = init?.method === 'POST'
    if (url.endsWith('/requirements')) {
      if (post) return (extract ?? extracted)()
      return json({ extracted: requirements !== null, requirements: requirements ?? [] })
    }
    if (url.endsWith('/match')) {
      if (post) return (compare ?? matched)()
      return json({ matched: matches !== null, model: 'claude-opus-5-5', results: matches ?? [] })
    }
    if (url.endsWith('/r1')) return json(document('r1', 'resume', RESUME_LINES))
    return json(document('j1', 'job', JOB_LINES))
  })
  vi.stubGlobal('fetch', fetch)
  return (path: string) =>
    fetch.mock.calls.filter(([url, init]) => url.endsWith(path) && init?.method === 'POST').length
}

async function highlighted(): Promise<string[]> {
  const preview = await screen.findByRole('region', { name: 'Parsed lines' })
  return within(preview)
    .queryAllByRole('listitem')
    .filter((item) => item.getAttribute('aria-current') === 'true')
    .map((item) => item.textContent ?? '')
}

const click = async (name: string | RegExp) =>
  fireEvent.click(await screen.findByRole('button', { name }))

describe('JobView requirements', () => {
  it('calls the model only when the button is pressed, then groups the requirements', async () => {
    const posts = fakeApi({ requirements: null })
    render(<JobView jobId="j1" />)

    const button = await screen.findByRole('button', { name: 'Extract requirements' })
    expect(posts('/requirements')).toBe(0)
    fireEvent.click(button)

    expect(await screen.findByText('Must have (1)')).toBeTruthy()
    expect(screen.getByText('Nice to have (1)')).toBeTruthy()
    expect(posts('/requirements')).toBe(1)
  })

  it('highlights the cited line of the job post when a requirement is chosen', async () => {
    fakeApi()
    render(<JobView jobId="j1" />)

    await click(/Kubernetes skill/)

    await waitFor(async () => expect(await highlighted()).toEqual(['3- Kubernetes is a plus']))
  })

  it('shows why extraction failed and lets the user try again', async () => {
    const extract = () => json({ detail: 'ANTHROPIC_API_KEY is not set.' }, 503)
    fakeApi({ requirements: null, extract })
    render(<JobView jobId="j1" />)

    await click('Extract requirements')

    expect((await screen.findByRole('alert')).textContent).toContain('ANTHROPIC_API_KEY')
    const retry = screen.getByRole('button', { name: 'Extract requirements' })
    expect(retry.hasAttribute('disabled')).toBe(false)
  })

  it('says so when a post has no requirements, and offers no comparison', async () => {
    fakeApi({ requirements: [] })
    render(<JobView jobId="j1" resumeId="r1" />)

    expect(await screen.findByText('No requirements were found in this post.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Compare with my resume' })).toBeNull()
  })
})

describe('JobView matching', () => {
  it('asks for a resume before offering to compare', async () => {
    fakeApi()
    render(<JobView jobId="j1" />)

    expect(await screen.findByText(/Add your resume to compare/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Compare with my resume' })).toBeNull()
  })

  it('sends the resume only on request, then shows verdicts and counts', async () => {
    const posts = fakeApi()
    render(<JobView jobId="j1" resumeId="r1" />)

    const button = await screen.findByRole('button', { name: 'Compare with my resume' })
    expect(screen.getByText(/sends your whole resume/)).toBeTruthy()
    expect(posts('/match')).toBe(0)
    fireEvent.click(button)

    const summary = 'Must-haves (1): 1 met · 0 partial · 0 not found'
    expect(await screen.findByText(summary)).toBeTruthy()
    expect(screen.getByRole('button', { name: /^Met Python or Go/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /^Not found Kubernetes/ })).toBeTruthy()
    expect(posts('/match')).toBe(1)
  })

  it('shows the resume lines and reason behind a verdict', async () => {
    fakeApi({ matches: MATCHES })
    render(<JobView jobId="j1" resumeId="r1" />)

    await click(/^Met Python or Go/)

    expect(screen.getByText(/Your resume shows Python APIs\. \(Resume line 2\.\)/)).toBeTruthy()
    await waitFor(async () => expect(await highlighted()).toEqual(['2Built APIs in Python']))

    await click('Job post')
    await waitFor(async () => expect(await highlighted()).toEqual(['2- Python or Go']))
  })

  it('shows the job post, not the resume, for a requirement with no evidence', async () => {
    fakeApi({ matches: MATCHES })
    render(<JobView jobId="j1" resumeId="r1" />)

    await click(/^Not found Kubernetes/)

    expect(screen.getByText('No Kubernetes is shown.')).toBeTruthy()
    await waitFor(async () => expect(await highlighted()).toEqual(['3- Kubernetes is a plus']))
  })

  it('shows why a comparison failed', async () => {
    fakeApi({ compare: () => json({ detail: "Anthropic's rate limit was reached." }, 429) })
    render(<JobView jobId="j1" resumeId="r1" />)

    await click('Compare with my resume')

    expect((await screen.findByRole('alert')).textContent).toContain('rate limit')
  })
})
