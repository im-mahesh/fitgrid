import { useEffect, useState } from 'react'

/**
 * A server result that costs money to create: `load` reads what is stored (free),
 * `create` is only called when the user asks.
 */
export function useStoredResult<T>(
  id: string,
  load: (id: string) => Promise<T>,
  create: (id: string) => Promise<T>,
  enabled = true,
) {
  const [data, setData] = useState<T | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    let stale = false
    load(id)
      .then((result) => !stale && setData(result))
      .catch((failure: Error) => !stale && setError(failure.message))
    return () => {
      stale = true
    }
  }, [id, load, enabled])

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setData(await create(id))
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return { data, busy, error, run }
}
