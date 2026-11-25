import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { DocumentDetail, DocumentList } from './api.ts'
import App from './App.tsx'

function document(id: string, kind: 'resume' | 'job', title: string): DocumentDetail {
  const lines = [
    { number: 1, section: 'SKILLS', text: 'SKILLS' },
    { number: 2, section: 'SKILLS', text: 'Python, Docker' },
  ]
  return { id, kind, title, filename: null, line_count: 2, created_at: '2026-01-01T00:00:00Z', lines }
}

function json(body: unknown, status = 200): Response {
  const headers = { 'content-type': 'application/json' }
  return new Response(JSON.stringify(body), { status, headers })
}

/** A tiny in-memory stand-in for the API. */
function fakeApi(initial: Partial<DocumentList> = {}, uploadError?: string) {
  const state: DocumentList = { resume: null, jobs: [], ...initial }
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    if (url === '/api/health') {
      return json({ status: 'ok', database: { reachable: true, pgvector_version: '0.8.0' } })
    }
    if (url === '/api/resume' && method === 'PUT') {
      if (uploadError) return json({ detail: uploadError }, 400)
      state.resume = document('r1', 'resume', 'Pasted resume')
      return json(state.resume)
    }
    if (url === '/api/documents' && method === 'DELETE') {
      state.resume = null
      state.jobs = []
      return new Response(null, { status: 204 })
    }
    if (url === '/api/documents') return json(state)
    if (url === '/api/overview') return json({ resume_id: state.resume?.id ?? null, jobs: [] })
    return json(document('r1', 'resume', 'Pasted resume'))
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function pasteResume(text: string) {
  fireEvent.change(screen.getByLabelText('Paste resume text'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Add pasted resume' }))
}

describe('App', () => {
  it('uploads a pasted resume and shows the numbered lines it was read as', async () => {
    fakeApi()
    render(<App />)

    pasteResume('SKILLS\nPython, Docker')

    const preview = await screen.findByRole('region', { name: 'Parsed lines' })
    expect(await within(preview).findByText('Python, Docker')).toBeTruthy()
    expect(within(preview).getByText('2')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Remove Pasted resume' })).toBeTruthy()
  })

  it('shows the message the API returns when an upload is rejected', async () => {
    fakeApi({}, 'No text found. Scanned or image-only PDFs aren’t supported.')
    render(<App />)

    pasteResume('x')

    expect((await screen.findByRole('alert')).textContent).toContain('No text found')
  })

  it('rejects an unsupported file without calling the API', async () => {
    const fetch = fakeApi()
    render(<App />)
    const callsBefore = fetch.mock.calls.length

    const file = new File(['PK'], 'cv.docx')
    fireEvent.change(screen.getByLabelText('Upload resume file'), { target: { files: [file] } })

    expect((await screen.findByRole('alert')).textContent).toContain('Unsupported file type')
    expect(fetch.mock.calls.length).toBe(callsBefore)
  })

  it('stops offering the job form once five jobs exist', async () => {
    const jobs = [1, 2, 3, 4, 5].map((n) => document(`j${n}`, 'job', `Job ${n}`))
    fakeApi({ jobs })
    render(<App />)

    expect(await screen.findByText('Jobs (5/5)')).toBeTruthy()
    expect(screen.queryByLabelText('Paste job text')).toBeNull()
    expect(screen.getByText('Remove a job to add another.')).toBeTruthy()
  })

  it('needs two clicks to delete everything', async () => {
    const fetch = fakeApi({ resume: document('r1', 'resume', 'My CV') })
    render(<App />)
    await screen.findByRole('button', { name: 'Remove My CV' })
    const deletes = () => fetch.mock.calls.filter(([, init]) => init?.method === 'DELETE')

    fireEvent.click(screen.getByRole('button', { name: 'Delete all my data' }))
    expect(deletes()).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Click again to delete everything' }))

    await waitFor(() => expect(screen.queryByRole('button', { name: 'Remove My CV' })).toBeNull())
    expect(deletes()).toHaveLength(1)
  })
})
