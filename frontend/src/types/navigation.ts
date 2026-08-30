import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  /** Route path, e.g. "/mission-control". */
  path: string
  label: string
  icon: LucideIcon
  /** Optional grouping header rendered above the item. */
  section?: string
  /** Feature not yet implemented — rendered with a "soon" affordance. */
  upcoming?: boolean
}
