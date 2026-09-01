import type { MessageKey } from '@/i18n/messages'
import type { Lot } from '@/types/domain'

/**
 * Word why a lot is blocked, in the reader's language.
 *
 * A lot carries two kinds of reason. One the services composed - a failed
 * inspection, a quantity gap - which arrives as a key plus its figures and is
 * worded here. One a manager typed, which arrives as a sentence and is shown
 * exactly as written: those are their words, and translating them would be
 * putting words in their mouth.
 */
export function blockingReason(
  lot: Pick<Lot, 'blocked_reason' | 'blocked_reason_key' | 'blocked_reason_values'>,
  t: (key: MessageKey, values?: Record<string, string | number>) => string,
): string | null {
  if (!lot.blocked_reason_key) return lot.blocked_reason
  const key = lot.blocked_reason_key as MessageKey
  const worded = t(key, lot.blocked_reason_values)
  // No translation yet: the recorded sentence is better than a raw key.
  return worded === key ? lot.blocked_reason : worded
}
