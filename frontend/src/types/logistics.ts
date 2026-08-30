/**
 * UI-level vocabulary.
 *
 * Domain shapes now come from the backend contract in `domain.ts`; this module
 * only keeps the presentation token used by the design system.
 */

/** Functional severity shared by every status indicator in the UI. */
export type Severity = 'ok' | 'warn' | 'crit' | 'info'
