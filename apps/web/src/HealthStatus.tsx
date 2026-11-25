import { useEffect, useState } from 'react'
import { fetchHealth, type Health } from './api.ts'
import styles from './HealthStatus.module.css'

function describe(health: Health): string {
  const { reachable, pgvector_version: pgvector } = health.database
  if (!reachable) return 'The API is up, but the database is unreachable.'
  if (!pgvector) return 'The database is up, but pgvector is not installed.'
  return `API and database are healthy (pgvector ${pgvector}).`
}

export function HealthStatus() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setError('Cannot reach the API.'))
  }, [])

  if (error) return <p className={`${styles.status} ${styles.bad}`}>{error}</p>
  if (!health) return <p className={styles.status}>Checking the API…</p>
  const tone = health.status === 'ok' ? styles.good : styles.bad
  return <p className={`${styles.status} ${tone}`}>{describe(health)}</p>
}
