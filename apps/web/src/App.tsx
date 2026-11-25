import { useState } from 'react'
import {
  addJob,
  deleteAllDocuments,
  deleteDocument,
  uploadResume,
  type DocumentDetail,
  type DocumentInput,
  type DocumentSummary,
} from './api.ts'
import styles from './App.module.css'
import { DeleteAllButton } from './components/DeleteAllButton.tsx'
import { DocumentCard } from './components/DocumentCard.tsx'
import { DocumentForm } from './components/DocumentForm.tsx'
import { LinesPreview } from './components/LinesPreview.tsx'
import { HealthStatus } from './HealthStatus.tsx'
import { useDocuments } from './useDocuments.ts'

const MAX_JOBS = 5

export default function App() {
  const { documents, error, refresh } = useDocuments()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const resume = documents?.resume ?? null
  const jobs = documents?.jobs ?? []
  const selected = [resume, ...jobs].find((d) => d?.id === selectedId)

  async function save(upload: (input: DocumentInput) => Promise<DocumentDetail>, input: DocumentInput) {
    const saved = await upload(input)
    await refresh()
    setSelectedId(saved.id)
  }

  async function remove(action: () => Promise<void>) {
    setActionError(null)
    try {
      await action()
    } catch (failure) {
      setActionError((failure as Error).message)
    }
    await refresh()
  }

  const card = (document: DocumentSummary) => (
    <DocumentCard
      key={document.id}
      document={document}
      selected={document.id === selectedId}
      onSelect={() => setSelectedId(document.id)}
      onRemove={() => remove(() => deleteDocument(document.id))}
    />
  )

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.name}>FitGrid</h1>
          <p className={styles.tagline}>See what your resume proves for each job, line by line.</p>
        </div>
        <DeleteAllButton onConfirm={() => remove(deleteAllDocuments)} />
      </header>

      {(error ?? actionError) && (
        <p className={styles.error} role="alert">
          {error ?? actionError}
        </p>
      )}

      <div className={styles.columns}>
        <div className={styles.inputs}>
          <section aria-label="Resume" className={styles.section}>
            <h2>Your resume</h2>
            {resume && card(resume)}
            <DocumentForm noun="resume" onSubmit={(input) => save(uploadResume, input)} />
          </section>

          <section aria-label="Jobs" className={styles.section}>
            <h2>
              Jobs ({jobs.length}/{MAX_JOBS})
            </h2>
            {jobs.map(card)}
            {jobs.length < MAX_JOBS ? (
              <DocumentForm noun="job" askForTitle onSubmit={(input) => save(addJob, input)} />
            ) : (
              <p className={styles.note}>Remove a job to add another.</p>
            )}
          </section>

          <p className={styles.note}>
            Documents are stored in this app&apos;s database. Nothing is sent to an AI model yet.
          </p>
          <HealthStatus />
        </div>

        <main className={styles.preview}>
          {selected ? (
            <LinesPreview key={selected.id} documentId={selected.id} />
          ) : (
            <p className={styles.note}>
              Add your resume and a job, then select one to see how it was read.
            </p>
          )}
        </main>
      </div>
    </div>
  )
}
