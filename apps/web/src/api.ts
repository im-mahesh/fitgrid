export interface Health {
  status: 'ok' | 'degraded'
  database: { reachable: boolean; pgvector_version: string | null }
}

/** The API answers 503 with the same body when degraded, so that is a result, not an error. */
export async function fetchHealth(): Promise<Health> {
  const response = await fetch('/api/health')
  const isHealthBody =
    (response.ok || response.status === 503) &&
    response.headers.get('content-type')?.includes('application/json')
  if (!isHealthBody) {
    throw new Error(`Health check failed (${response.status})`)
  }
  return response.json()
}
