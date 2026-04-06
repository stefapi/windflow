/**
 * Format utilities for human-readable display
 */

/**
 * Format bytes into human-readable string (e.g., "1.5 GB", "512.0 MB").
 * Returns '-' if the value is null or undefined, "0 B" if zero.
 *
 * @param bytes - The byte value to format (number, null, or undefined)
 * @returns Formatted string
 */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return '-'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const value = bytes / Math.pow(k, i)
  return `${value.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}
