import { useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react'
import type { DocumentInput } from '../api.ts'
import { ACCEPTED_EXTENSIONS, validateFile } from '../validateFile.ts'
import styles from './DocumentForm.module.css'

interface DocumentFormProps {
  /** "resume" or "job", used in labels. */
  noun: string
  askForTitle?: boolean
  onSubmit: (input: DocumentInput) => Promise<void>
}

/** Upload (button or drag and drop) or paste one document. */
export function DocumentForm({ noun, askForTitle, onSubmit }: DocumentFormProps) {
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  async function submit(input: DocumentInput) {
    setBusy(true)
    setError(null)
    try {
      await onSubmit({ ...input, title: title.trim() || undefined })
      setText('')
      setTitle('')
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function submitFile(file: File | undefined) {
    if (!file || busy) return
    const problem = validateFile(file)
    if (problem) setError(problem)
    else void submit({ file })
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    submitFile(event.dataTransfer.files[0])
  }

  function handleChoose(event: ChangeEvent<HTMLInputElement>) {
    submitFile(event.target.files?.[0])
    event.target.value = ''
  }

  function handlePaste(event: FormEvent) {
    event.preventDefault()
    if (text.trim()) void submit({ text })
  }

  return (
    <form className={styles.form} onSubmit={handlePaste}>
      {askForTitle && (
        <input
          className={styles.field}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Job title (optional)"
          aria-label={`${noun} title`}
          maxLength={80}
        />
      )}
      <label
        className={`${styles.drop} ${dragging ? styles.dragging : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <span>Drop a {noun} file or click to choose (PDF, TXT, MD)</span>
        <input
          type="file"
          className={styles.file}
          accept={ACCEPTED_EXTENSIONS.join(',')}
          onChange={handleChoose}
          disabled={busy}
          aria-label={`Upload ${noun} file`}
        />
      </label>
      <textarea
        className={styles.field}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={`…or paste the ${noun} text`}
        aria-label={`Paste ${noun} text`}
        rows={4}
        maxLength={50_000}
      />
      <button type="submit" className={styles.button} disabled={busy || !text.trim()}>
        {busy ? 'Reading…' : `Add pasted ${noun}`}
      </button>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
