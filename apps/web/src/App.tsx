import { useState } from 'react'
import {
  addJob,
  deleteAllDocuments,
  deleteDocument,
  uploadResume,
  type DocumentDetail,
  type DocumentInput,
  type DocumentSummary,
  type Source,
} from './api.ts'
import styles from './App.module.css'
import { sourceLabel } from './citations.ts'
import { ChatPanel } from './components/ChatPanel.tsx'
import { DeleteAllButton } from './components/DeleteAllButton.tsx'
import { DocumentCard } from './components/DocumentCard.tsx'
import { DocumentForm } from './components/DocumentForm.tsx'
import { FitGrid } from './components/FitGrid.tsx'
import { JobView } from './components/JobView.tsx'
import { LinesPreview } from './components/LinesPreview.tsx'
import { HealthStatus } from './HealthStatus.tsx'
import { useDocuments } from './useDocuments.ts'

const MAX_JOBS = 5

export default function App() {
  const { documents, error, refresh } = useDocuments()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [cited, setCited] = useState<Source | null>(null) // a line a chat answer points to
  const [chatSession, setChatSession] = useState(0)
  const resume = documents?.resume ?? null
  const jobs = documents?.jobs ?? []
  const selected = [resume, ...jobs].find((d) => d?.id === selectedId)

  function show(id: string | null) {
    setCited(null)
    setSelectedId(id)
  }

  // Removing or replacing a document renumbers jobs and breaks citations, so start the chat again.
  function restartChat() {
    setCited(null)
    setChatSession((session) => session + 1)
  }

  async function save(upload: (input: DocumentInput) => Promise<DocumentDetail>, input: DocumentInput) {
    const replacesResume = upload === uploadResume && resume !== null
    const saved = await upload(input)
    if (replacesResume) restartChat()
    await refresh()
    show(saved.id)
  }

  async function remove(action: () => Promise<void>) {
    setActionError(null)
    try {
      await action()
      restartChat()
    } catch (failure) {
      setActionError((failure as Error).message)
    }
    await refresh()
  }

  const card = (document: DocumentSummary, number?: number) => (
    <DocumentCard
      key={document.id}
      document={document}
      number={number}
      selected={document.id === selectedId}
      onSelect={() => show(document.id)}
      onRemove={() => remove(() => deleteDocument(document.id))}
    />
  )

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.name}>Career Intelligent System</h1>
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
          <button
            type="button"
            className={styles.gridButton}
            aria-pressed={!selected}
            onClick={() => show(null)}
          >
            Fit grid
          </button>

          <section aria-label="Resume" className={styles.section}>
            <h2>Your resume</h2>
            {resume && card(resume)}
            <DocumentForm noun="resume" onSubmit={(input) => save(uploadResume, input)} />
          </section>

          <section aria-label="Jobs" className={styles.section}>
            <h2>
              Jobs ({jobs.length}/{MAX_JOBS})
            </h2>
            {jobs.map((job, index) => card(job, index + 1))}
            {jobs.length < MAX_JOBS ? (
              <DocumentForm noun="job" askForTitle onSubmit={(input) => save(addJob, input)} />
            ) : (
              <p className={styles.note}>Remove a job to add another.</p>
            )}
          </section>

          <p className={styles.note}>
            Documents are stored in this app&apos;s database. A job post is sent to Anthropic when you
            extract its requirements, and resume lines only when you compare it with a job or ask a
            question.
          </p>
          <HealthStatus />
        </div>

        <main className={styles.preview}>
          {cited ? (
            <>
              <button type="button" className={styles.back} onClick={() => setCited(null)}>
                ← Back
              </button>
              <LinesPreview
                key={cited.document_id}
                documentId={cited.document_id}
                highlighted={[cited.line_number]}
                hint={`Cited in the chat: ${sourceLabel(cited)}.`}
              />
            </>
          ) : selected?.kind === 'job' ? (
            <JobView
              key={`${selected.id}:${resume?.id}`}
              jobId={selected.id}
              resumeId={resume?.id}
            />
          ) : selected ? (
            <LinesPreview key={selected.id} documentId={selected.id} />
          ) : (
            // Remounts, and so reloads, whenever a document is added or removed.
            <FitGrid key={[resume, ...jobs].map((d) => d?.id).join()} />
          )}
        </main>

        <aside className={styles.chat}>
          <ChatPanel
            key={chatSession}
            hasResume={resume !== null}
            jobCount={jobs.length}
            openJobId={selected?.kind === 'job' ? selected.id : undefined}
            onCite={setCited}
          />
        </aside>
      </div>
    </div>
  )
}
