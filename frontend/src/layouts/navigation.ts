import {
  BarChart3,
  BellRing,
  Library,
  Boxes,
  ClipboardCheck,
  FileSpreadsheet,
  FileText,
  Factory,
  LayoutDashboard,
  PackageSearch,
  Route,
  Settings,
  Users,
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
    //: The backlog, badged with what nobody owns. Mission Control keeps its
    //: shortlist of eight; this is where a manager works through the rest.
    path: '/alertes',
    labelKey: 'alerts.title',
    icon: BellRing,
    badge: 'alerts',
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
  //: Reference tables, not settings: nothing here is configured.
  { path: '/referentiel', labelKey: 'ref.title', icon: Library },
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
    //: Who signs in the workbook. Administration, so it belongs in Systeme.
    path: '/equipe',
    labelKey: 'team.title',
    icon: Users,
    sectionKey: 'nav.section.system',
  },
  {
    path: '/settings',
    labelKey: 'nav.settings',
    icon: Settings,
  },
]
