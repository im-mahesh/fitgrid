import { useCallback, useEffect, useState } from 'react'
import { listDocuments, type DocumentList } from './api.ts'

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentList | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setDocuments(await listDocuments())
      setError(null)
    } catch (failure) {
      setError((failure as Error).message)
    }
  }, [])

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch((failure: Error) => setError(failure.message))
  }, [])

  return { documents, error, refresh }
}
