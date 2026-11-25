// Mirrors the API's limits so the user hears about a problem before uploading.
export const ACCEPTED_EXTENSIONS = ['.pdf', '.txt', '.md']
export const MAX_FILE_BYTES = 5 * 1024 * 1024

export function validateFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return `Unsupported file type. Allowed: ${ACCEPTED_EXTENSIONS.join(', ')}.`
  }
  if (file.size > MAX_FILE_BYTES) return 'The file is too large. The maximum size is 5 MB.'
  return null
}
