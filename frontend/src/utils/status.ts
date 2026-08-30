import type { Severity } from '@/types'
import type {
  ApiSeverity,
  InspectionResult,
  LotStatus,
  ProductionRequestStatus,
  ReceptionStatus,
  RiskLevel,
} from '@/types/domain'

/**
 * Single source of truth for functional colour semantics:
 * green = normal/validated, orange = attention, red = critical/blocked,
 * blue = information/movement.
 */
export const severityStyles: Record<
  Severity,
  { dot: string; text: string; border: string; bg: string; bar: string; label: string }
> = {
  ok: {
    dot: 'bg-ok',
    text: 'text-ok-soft',
    border: 'border-ok/35',
    bg: 'bg-ok/10',
    bar: 'bg-ok',
    label: 'Normal',
  },
  warn: {
    dot: 'bg-warn',
    text: 'text-warn-soft',
    border: 'border-warn/35',
    bg: 'bg-warn/10',
    bar: 'bg-warn',
    label: 'Attention',
  },
  crit: {
    dot: 'bg-crit',
    text: 'text-crit-soft',
    border: 'border-crit/35',
    bg: 'bg-crit/10',
    bar: 'bg-crit',
    label: 'Critical',
  },
  info: {
    dot: 'bg-info',
    text: 'text-info-soft',
    border: 'border-info/35',
    bg: 'bg-info/10',
    bar: 'bg-info',
    label: 'Information',
  },
}

/** Backend severity vocabulary -> UI severity token. */
export function toSeverity(value: ApiSeverity | string | null | undefined): Severity {
  switch (value) {
    case 'OK':
      return 'ok'
    case 'WARNING':
      return 'warn'
    case 'CRITICAL':
      return 'crit'
    default:
      return 'info'
  }
}

/** Lot lifecycle state -> functional severity. */
export const lotStatusSeverity: Record<LotStatus, Severity> = {
  PENDING_INSPECTION: 'info',
  INSPECTION_IN_PROGRESS: 'info',
  QUALITY_PENDING: 'warn',
  APPROVED: 'ok',
  REJECTED: 'crit',
  RED_CAGE: 'crit',
  STORED: 'ok',
  CONSUMED: 'info',
}

export const requestStatusSeverity: Record<ProductionRequestStatus, Severity> = {
  DRAFT: 'info',
  SUBMITTED: 'warn',
  APPROVED: 'ok',
  PREPARING: 'info',
  READY: 'info',
  ISSUED: 'ok',
  REJECTED: 'crit',
  CANCELLED: 'warn',
}

export const receptionStatusSeverity: Record<ReceptionStatus, Severity> = {
  ACCEPTED: 'ok',
  ACCEPTED_WITH_TOLERANCE: 'warn',
  QUANTITY_MISMATCH: 'crit',
}

export const inspectionResultSeverity: Record<InspectionResult, Severity> = {
  CONFORM: 'ok',
  NON_CONFORM: 'crit',
}

export const riskSeverity: Record<RiskLevel, Severity> = {
  LOW: 'ok',
  MEDIUM: 'warn',
  HIGH: 'crit',
}

/** Priority 1 is the most urgent. */
export const prioritySeverity: Record<number, Severity> = {
  1: 'crit',
  2: 'warn',
  3: 'info',
}
