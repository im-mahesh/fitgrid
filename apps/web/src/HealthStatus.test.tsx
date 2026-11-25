import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HealthStatus } from './HealthStatus.tsx'

function respondWith(status: number, body: unknown) {
  const headers = { 'content-type': 'application/json' }
  const response = new Response(JSON.stringify(body), { status, headers })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
}

describe('HealthStatus', () => {
  it('reports a healthy API and database', async () => {
    respondWith(200, { status: 'ok', database: { reachable: true, pgvector_version: '0.8.0' } })
    render(<HealthStatus />)
    expect(await screen.findByText(/healthy \(pgvector 0\.8\.0\)/)).toBeTruthy()
  })

  it('explains a degraded response instead of calling the API unreachable', async () => {
    respondWith(503, { status: 'degraded', database: { reachable: false, pgvector_version: null } })
    render(<HealthStatus />)
    expect(await screen.findByText(/database is unreachable/)).toBeTruthy()
  })

  it('says so when the API cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')))
    render(<HealthStatus />)
    expect(await screen.findByText('Cannot reach the API.')).toBeTruthy()
  })
})
