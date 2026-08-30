/** Join conditional class names (dependency-free `clsx`). */
export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(' ')
}
