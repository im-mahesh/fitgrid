// Types are generated from the API: run `bash scripts/gen-types.sh` after changing a model.
import type { components } from './schema.d.ts'

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

export const deleteAllDocuments = () => request<void>('/documents', { method: 'DELETE' })
