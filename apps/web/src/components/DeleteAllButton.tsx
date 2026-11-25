import { useState } from 'react'
import styles from './DeleteAllButton.module.css'

/** Two clicks, so personal data isn't wiped by accident. */
export function DeleteAllButton({ onConfirm }: { onConfirm: () => void }) {
  const [armed, setArmed] = useState(false)

  return (
    <button
      type="button"
      className={`${styles.button} ${armed ? styles.armed : ''}`}
      onClick={() => {
        if (armed) onConfirm()
        setArmed(!armed)
      }}
      onBlur={() => setArmed(false)}
    >
      {armed ? 'Click again to delete everything' : 'Delete all my data'}
    </button>
  )
}
