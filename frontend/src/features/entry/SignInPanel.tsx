import { useState, type FormEvent } from 'react'
import { KeyRound, Loader2, ShieldAlert } from 'lucide-react'

import { useI18n } from '@/i18n/I18nProvider'
import { useSession } from '@/hooks/useSession'

/**
 * The door into the supervision site.
 *
 * The proof is the validation code the responsible already uses to sign a line
 * in the workbook - one secret, checked by the same rule on both sides. A code
 * revoked in the plant stops working here at the same moment.
 *
 * The refusal for a valid-but-wrong-role account says so explicitly rather than
 * pretending the credentials were wrong: a chef réception typing their real
 * code deserves to be told this site is not theirs, not left doubting their
 * own matricule.
 */
export function SignInPanel() {
  const { t } = useI18n()
  const { signIn } = useSession()
  const [matricule, setMatricule] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()

    // Read the fields from the form, not only from state. A browser password
    // manager fills the inputs without firing React's change event, so the
    // state stays empty while the boxes look full - and the form refuses to
    // submit with nothing on screen explaining why.
    const form = event.currentTarget as HTMLFormElement
    const data = new FormData(form)
    const typedMatricule = String(data.get('matricule') ?? matricule).trim().toUpperCase()
    const typedCode = String(data.get('code') ?? code).trim()

    if (!typedMatricule || !typedCode) {
      setError(t('auth.missing'))
      return
    }

    setBusy(true)
    setError(null)
    const failure = await signIn(typedMatricule, typedCode)
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <form
      onSubmit={submit}
      className="panel w-full max-w-sm space-y-4 p-6 shadow-lift backdrop-blur-sm"
    >
      <div className="border-b border-line pb-4">
        <h2 className="text-base font-semibold tracking-tight text-ink">{t('auth.title')}</h2>
        <p className="mt-1 text-2xs leading-relaxed text-ink-3">{t('auth.subtitle')}</p>
      </div>

      <label className="block">
        <span className="eyebrow">{t('auth.matricule')}</span>
        <input
          name="matricule"
          value={matricule}
          onChange={(event) => setMatricule(event.target.value)}
          autoComplete="username"
          autoFocus
          placeholder="LM-001"
          className="numeric mt-1.5 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-3/60 focus:border-accent"
        />
      </label>

      <label className="block">
        <span className="eyebrow">{t('auth.code')}</span>
        <div className="relative mt-1.5">
          <KeyRound
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3"
            aria-hidden="true"
          />
          <input
            name="code"
            type="password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            autoComplete="current-password"
            className="numeric w-full rounded-lg border border-line bg-elevated py-2 pl-9 pr-3 text-sm text-ink outline-none transition-colors focus:border-accent"
          />
        </div>
      </label>

      {error && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-2xs leading-relaxed text-crit-soft"
        >
          <ShieldAlert className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-canvas transition-all duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {t('auth.submit')}
      </button>

      <p className="text-center text-[11px] leading-relaxed text-ink-3">{t('auth.hint')}</p>
    </form>
  )
}
