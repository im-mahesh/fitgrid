import { useState } from 'react'
import { LinesPreview } from './LinesPreview.tsx'
import { RequirementsPanel } from './RequirementsPanel.tsx'

/** A job's requirements, above the post they came from. Choosing one highlights its lines. */
export function JobView({ jobId }: { jobId: string }) {
  const [highlighted, setHighlighted] = useState<number[]>([])
  return (
    <>
      <RequirementsPanel jobId={jobId} highlighted={highlighted} onShowLines={setHighlighted} />
      <LinesPreview documentId={jobId} highlighted={highlighted} />
    </>
  )
}
