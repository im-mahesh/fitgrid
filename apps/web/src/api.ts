// Types are generated from the API: run `bash scripts/gen-types.sh` after changing a model.
import type { components } from './schema.d.ts'
import { splitEvents } from './sse.ts'

type Schemas = components['schemas']

export type Health = Schemas['HealthResponse']
export type DocumentList = Schemas['DocumentList']
export type DocumentSummary = Schemas['DocumentSummary']
export type DocumentDetail = Schemas['DocumentDetail']
export type Line = Schemas['Line']
export type Requirement = Schemas['Requirement']
export type RequirementsResponse = Schemas['RequirementsResponse']
export type Match = Schemas['Match']
export type MatchResponse = Schemas['MatchResponse']
export type Verdict = Match['verdict']
export type Overview = Schemas['Overview']
export type JobOverview = Schemas['JobOverview']

/** What the user gave us: exactly one of a file or pasted text, plus an optional job title. */
export interface DocumentInput {
  file?: File
  text?: string
  title?: string
}

async function errorMessage(response: Response): Promise<string> {
  if (response.status === 413) return 'The file is too large.'
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // Not JSON (for example a proxy error page).
  }
  return `Request failed (${response.status}).`
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`/api${path}`, init)
  } catch {
    throw new Error('Cannot reach the API.')
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init)
  if (!response.ok) throw new Error(await errorMessage(response))
  if (response.status === 204) return undefined as T
  return response.json()
}

function form({ file, text, title }: DocumentInput): FormData {
  const data = new FormData()
  if (file) data.append('file', file)
  if (text) data.append('text', text)
  if (title) data.append('title', title)
  return data
}

/** The API answers 503 with the same body when degraded, so that is a result, not an error. */
export async function fetchHealth(): Promise<Health> {
  const response = await send('/health')
  const isHealthBody =
    (response.ok || response.status === 503) &&
    response.headers.get('content-type')?.includes('application/json')
  if (!isHealthBody) throw new Error(`Health check failed (${response.status})`)
  return response.json()
}

export const listDocuments = () => request<DocumentList>('/documents')

export const getDocument = (id: string) => request<DocumentDetail>(`/documents/${id}`)

export const uploadResume = (input: DocumentInput) =>
  request<DocumentDetail>('/resume', { method: 'PUT', body: form(input) })

export const addJob = (input: DocumentInput) =>
  request<DocumentDetail>('/jobs', { method: 'POST', body: form(input) })

export const deleteDocument = (id: string) =>
  request<void>(`/documents/${id}`, { method: 'DELETE' })

export const getRequirements = (jobId: string) =>
  request<RequirementsResponse>(`/jobs/${jobId}/requirements`)

/** Calls Claude (billed) unless a stored result exists. */
export const extractRequirements = (jobId: string) =>
  request<RequirementsResponse>(`/jobs/${jobId}/requirements`, { method: 'POST' })

export const getMatch = (jobId: string) => request<MatchResponse>(`/jobs/${jobId}/match`)

/** Sends the resume to Claude (billed) unless a stored result exists. */
export const runMatch = (jobId: string) =>
  request<MatchResponse>(`/jobs/${jobId}/match`, { method: 'POST' })

export const getOverview = () => request<Overview>('/overview')

export const deleteAllDocuments = () => request<void>('/documents', { method: 'DELETE' })

export type ChatMessage = Schemas['ChatMessage']
export type ChatRequest = Schemas['ChatRequest']
export type Source = Schemas['Source']
export type ChatStreamEvent = Schemas['ChatStreamEvent']

/**
 * Ask a question (billed). Calls `onEvent` for each event as it arrives, and
 * throws if the request is refused or the stream stops without finishing.
 */
export async function streamChat(
  body: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await send('/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) throw new Error(await errorMessage(response))

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let finished = false
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const { data, rest } = splitEvents(buffer + value)
    buffer = rest
    for (const payload of data) {
      const event = JSON.parse(payload) as ChatStreamEvent
      finished ||= event.type === 'done' || event.type === 'error'
      onEvent(event)
    }
  }
  if (!finished) throw new Error('The answer was interrupted.')
}
