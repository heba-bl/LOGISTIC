import {
  BarChart3,
  Boxes,
  ClipboardCheck,
  FileSpreadsheet,
  FileText,
  Factory,
  LayoutDashboard,
  PackageSearch,
  Route,
  Settings,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'

import type { MessageKey } from '@/i18n/messages'
import type { NavItem } from '@/types'

/**
 * Single source of truth for the sidebar and the router.
 *
 * Labels are translation keys, never literals: adding a module here wires the
 * navigation, the router and both languages at once.
 */
export interface NavEntry extends Omit<NavItem, 'label' | 'section'> {
  labelKey: MessageKey
  sectionKey?: MessageKey
  /** Sub-destinations, shown nested and only while the rail is expanded. */
  children?: { path: string; labelKey: MessageKey }[]
  /** Which live counter, if any, badges this entry. */
  badge?: 'alerts' | 'pending'
}

export const NAV_ITEMS: NavEntry[] = [
  {
    path: '/mission-control',
    labelKey: 'nav.missionControl',
    icon: LayoutDashboard,
    sectionKey: 'nav.section.supervision',
  },

  {
    path: '/donnees',
    labelKey: 'nav.data',
    icon: FileSpreadsheet,
    sectionKey: 'nav.section.operations',
  },
  { path: '/receiving', labelKey: 'nav.receiving', icon: PackageSearch },
  { path: '/inspection', labelKey: 'nav.inspection', icon: ClipboardCheck, badge: 'pending' },
  { path: '/quality', labelKey: 'nav.quality', icon: ShieldCheck },
  { path: '/warehouse', labelKey: 'nav.warehouse', icon: Boxes },
  { path: '/production', labelKey: 'nav.production', icon: Factory },

  {
    path: '/traceability',
    labelKey: 'nav.traceability',
    icon: Route,
    sectionKey: 'nav.section.analytics',
  },
  { path: '/rapports', labelKey: 'nav.reports', icon: FileText },
  {
    path: '/analytics',
    labelKey: 'nav.analytics',
    icon: BarChart3,
    children: [
      { path: '/analytics', labelKey: 'nav.analytics.global' },
      { path: '/analytics/stock', labelKey: 'nav.analytics.stock' },
      { path: '/analytics/qualite', labelKey: 'nav.analytics.quality' },
      { path: '/analytics/production', labelKey: 'nav.analytics.production' },
    ],
  },
  { path: '/ai-assistant', labelKey: 'nav.ai', icon: Sparkles },

  {
    path: '/settings',
    labelKey: 'nav.settings',
    icon: Settings,
    sectionKey: 'nav.section.system',
  },
]
