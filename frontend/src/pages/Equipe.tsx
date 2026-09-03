import { useMemo, useState } from 'react'
import { FileSpreadsheet, KeyRound, RefreshCw, UserPlus, Users } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
import {
  FilterBar,
  KpiRow,
  ReportTable,
  matches,
  useFilterState,
  type SupervisionKpi,
} from '@/features/supervision/shell'
import { useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { teamApi, type TeamMember } from '@/services/slcc.service'
import { cn } from '@/utils/cn'

/**
 * Who signs in the shared workbook.
 *
 * Until now the roster lived only in the seed script: adding a storeman or
 * retiring a leaver meant wiping the database and starting over. That is fine
 * while preparing a demonstration and impossible in a plant.
 *
 * Nothing here is ever deleted. A user who has signed a line stays for good,
 * because the audit trail names them and a trail that can lose its author is
 * not a trail. A departure is a deactivation.
 */
export default function Equipe() {
  const { t, ts, formatNumber } = useI18n()
  const toast = useToast()
  const team = useApiResource(() => teamApi.list(), [])
  const filters = useFilterState(['role', 'state'])
  const [issued, setIssued] = useState<{ matricule: string; code: string } | null>(null)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [regenerating, setRegenerating] = useState(false)

  const members = team.data ?? []

  const roles = useMemo(
    () => [...new Set(members.map((m) => m.role?.name).filter(Boolean))].sort() as string[],
    [members],
  )

  const visible = useMemo(
    () =>
      members.filter(
        (member) =>
          matches(
            [member.employee_number, member.full_name, member.service, member.role?.name],
            filters.search,
          ) &&
          (!filters.values.role || member.role?.name === filters.values.role) &&
          (!filters.values.state ||
            (filters.values.state === 'ACTIVE' ? member.is_active : !member.is_active)),
      ),
    [members, filters.search, filters.values.role, filters.values.state],
  )

  const validators = members.filter((m) => m.can_validate && m.is_active)

  const kpis: SupervisionKpi[] = [
    {
      key: 'active',
      label: t('team.kpi.active'),
      value: formatNumber(members.filter((m) => m.is_active).length),
      hint: t('team.kpi.activeHint'),
      severity: 'OK',
    },
    {
      key: 'validators',
      label: t('team.kpi.validators'),
      value: formatNumber(validators.length),
      hint: t('team.kpi.validatorsHint'),
      severity: 'INFO',
    },
    {
      key: 'nocode',
      label: t('team.kpi.noCode'),
      value: formatNumber(validators.filter((m) => !m.has_code).length),
      hint: t('team.kpi.noCodeHint'),
      // A responsible with the right to sign and no code cannot sign at all.
      severity: validators.some((m) => !m.has_code) ? 'CRITICAL' : 'OK',
    },
    {
      key: 'inactive',
      label: t('team.kpi.inactive'),
      value: formatNumber(members.filter((m) => !m.is_active).length),
      hint: t('team.kpi.inactiveHint'),
      severity: 'INFO',
    },
  ]

  async function run(matricule: string, call: () => Promise<unknown>, message: string) {
    setBusy(matricule)
    try {
      const result = (await call()) as { code?: string | null } | undefined
      if (result?.code) setIssued({ matricule, code: result.code })
      toast.push({ severity: 'ok', title: message })
      await team.refresh()
    } catch (error) {
      toast.push({ severity: 'crit', title: String(error) })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('team.title')}
        description={t('team.subtitle')}
        actions={
          <button type="button" onClick={() => setAdding(true)} className="btn-primary">
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            {t('team.add')}
          </button>
        }
      />

      {/* The one moment the plain code exists. It is never stored and never
          returned again: losing it means issuing a new one, which is the right
          outcome - a code somebody can look up is a code somebody can borrow. */}
      {issued && (
        <div className="rise rounded-xl border border-ok/40 bg-ok/10 px-4 py-3">
          <p className="flex flex-wrap items-center gap-2 text-xs font-semibold text-ok-soft">
            <KeyRound className="h-4 w-4 shrink-0" aria-hidden="true" />
            {t('team.codeIssued', { matricule: issued.matricule })}
            <span className="numeric rounded-lg bg-panel px-3 py-1 text-sm tracking-widest text-ink">
              {issued.code}
            </span>
          </p>
          <p className="mt-1.5 text-2xs text-ink-2">{t('team.codeOnce')}</p>
          <button
            type="button"
            onClick={() => setIssued(null)}
            className="btn-ghost mt-2 h-8 px-3 text-[11px]"
          >
            {t('team.codeNoted')}
          </button>
        </div>
      )}

      {/* The workbook is a file, not a window: it carries the roster that was
          current when it was generated. Without this line somebody adds a
          storeman, he cannot sign, and nobody knows why. */}
      <div className="source-strip flex flex-wrap items-center gap-3">
        <span className="flex-1">{t('team.regenerateNotice')}</span>
        <button
          type="button"
          disabled={regenerating}
          onClick={async () => {
            setRegenerating(true)
            try {
              const done = await teamApi.regenerateWorkbook()
              toast.push({
                severity: 'ok',
                title: t('team.regenerated'),
                description: `${Math.round(done.size_bytes / 1024)} Ko · ${done.sheet_count}`,
              })
            } catch (caught) {
              toast.push({ severity: 'crit', title: String(caught) })
            } finally {
              setRegenerating(false)
            }
          }}
          className="btn-secondary shrink-0"
        >
          <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden="true" />
          {regenerating ? t('team.regenerating') : t('team.regenerate')}
        </button>
      </div>

      {team.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : team.error && !team.data ? (
        <div className="panel">
          <ErrorPanel message={team.error} onRetry={team.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          {adding && <AddForm onDone={() => setAdding(false)} onIssued={setIssued} refresh={team.refresh} />}

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={t('team.searchPlaceholder')}
            count={t('common.rowsShown', {
              shown: formatNumber(visible.length),
              total: formatNumber(members.length),
            })}
            onReset={filters.reset}
            selects={[
              {
                key: 'role',
                label: t('team.role'),
                value: filters.values.role,
                onChange: (value) => filters.set('role', value),
                options: roles.map((value) => ({ value, label: ts(value) })),
              },
              {
                key: 'state',
                label: t('common.status'),
                value: filters.values.state,
                onChange: (value) => filters.set('state', value),
                options: [
                  { value: 'ACTIVE', label: t('team.stateActive') },
                  { value: 'INACTIVE', label: t('team.stateInactive') },
                ],
              },
            ]}
          />

          <ChartCard
            title={t('team.list')}
            question={t('team.listQuestion')}
            bodyClassName="px-0 pb-0"
          >
            <ReportTable
              minWidth={980}
              columns={[
                { key: 'matricule', label: t('auth.matricule') },
                { key: 'name', label: t('team.name') },
                { key: 'role', label: t('team.role') },
                { key: 'zone', label: t('team.zone') },
                { key: 'code', label: t('team.code') },
                { key: 'state', label: t('common.status') },
                { key: 'actions', label: t('common.actions'), align: 'right' },
              ]}
              empty={
                visible.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      icon={<Users className="h-5 w-5" />}
                      title={t('team.noMatch')}
                      description={t('recv.emptyFiltered')}
                    />
                  </div>
                ) : undefined
              }
            >
              {visible.map((member) => (
                <tr key={member.id} className={cn(!member.is_active && 'opacity-55')}>
                  <td className="numeric font-medium text-ink">{member.employee_number}</td>
                  <td>{member.full_name}</td>
                  <td className="text-2xs">{ts(member.role?.name ?? '')}</td>
                  <td className="text-2xs">{member.zone ? ts(member.zone) : '—'}</td>
                  <td>
                    {!member.can_validate ? (
                      <span className="text-2xs text-ink-3">—</span>
                    ) : member.has_code ? (
                      <Badge severity="ok">{t('team.codeSet')}</Badge>
                    ) : (
                      <Badge severity="crit">{t('team.codeMissing')}</Badge>
                    )}
                  </td>
                  <td>
                    <Badge severity={member.is_active ? 'ok' : 'info'}>
                      {member.is_active ? t('team.stateActive') : t('team.stateInactive')}
                    </Badge>
                  </td>
                  <td>
                    <div className="flex justify-end gap-2">
                      {member.can_validate && member.is_active && (
                        <button
                          type="button"
                          disabled={busy === member.employee_number}
                          onClick={() =>
                            run(
                              member.employee_number,
                              () => teamApi.reissueCode(member.employee_number),
                              t('team.codeReissued'),
                            )
                          }
                          className="btn-ghost h-8 px-2.5 text-[11px]"
                        >
                          <RefreshCw className="h-3 w-3" aria-hidden="true" />
                          {t('team.reissue')}
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy === member.employee_number}
                        onClick={() =>
                          run(
                            member.employee_number,
                            () =>
                              member.is_active
                                ? teamApi.deactivate(member.employee_number)
                                : teamApi.activate(member.employee_number),
                            member.is_active ? t('team.deactivated') : t('team.activated'),
                          )
                        }
                        className={cn(
                          'h-8 px-2.5 text-[11px]',
                          member.is_active ? 'btn-ghost hover:text-crit' : 'btn-secondary',
                        )}
                      >
                        {member.is_active ? t('team.deactivate') : t('team.activate')}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </ReportTable>
          </ChartCard>
        </>
      )}
    </div>
  )
}

/** The add form. Kept inline: a modal for six fields is a modal too many. */
function AddForm({
  onDone,
  onIssued,
  refresh,
}: {
  onDone: () => void
  onIssued: (value: { matricule: string; code: string }) => void
  refresh: () => Promise<void>
}) {
  const { t } = useI18n()
  const toast = useToast()
  const roles = useApiResource(() => teamApi.list(), [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const available = useMemo(() => {
    const seen = new Map<string, boolean>()
    for (const member of roles.data ?? []) {
      if (member.role?.name) seen.set(member.role.name, member.can_validate)
    }
    return [...seen.entries()]
  }, [roles.data])

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true)
    setError(null)
    try {
      const result = await teamApi.create({
        employee_number: String(data.get('employee_number') ?? '').trim().toUpperCase(),
        first_name: String(data.get('first_name') ?? '').trim(),
        last_name: String(data.get('last_name') ?? '').trim(),
        role_name: String(data.get('role_name') ?? ''),
        zone: String(data.get('zone') ?? '') || undefined,
        service: String(data.get('service') ?? '').trim() || undefined,
      })
      if (result.code) {
        onIssued({ matricule: result.member.employee_number, code: result.code })
      }
      toast.push({ severity: 'ok', title: t('team.added') })
      await refresh()
      onDone()
    } catch (caught) {
      setError(String(caught))
    } finally {
      setBusy(false)
    }
  }

  const field =
    'h-[38px] w-full rounded-xl border border-line bg-elevated/60 px-3 text-xs text-ink outline-none transition-colors focus:border-accent focus:bg-panel'

  return (
    <form onSubmit={submit} className="panel space-y-3 p-5">
      <h2 className="text-sm font-semibold tracking-tight text-ink">{t('team.add')}</h2>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <label className="block">
          <span className="eyebrow">{t('auth.matricule')}</span>
          <input name="employee_number" required placeholder="WH-030" className={cn('numeric mt-1.5', field)} />
        </label>
        <label className="block">
          <span className="eyebrow">{t('team.firstName')}</span>
          <input name="first_name" required className={cn('mt-1.5', field)} />
        </label>
        <label className="block">
          <span className="eyebrow">{t('team.lastName')}</span>
          <input name="last_name" required className={cn('mt-1.5', field)} />
        </label>
        <label className="block">
          <span className="eyebrow">{t('team.role')}</span>
          <select name="role_name" required className={cn('mt-1.5 cursor-pointer', field)}>
            {available.map(([name, validates]) => (
              <option key={name} value={name}>
                {name}
                {validates ? ' ✓' : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="eyebrow">{t('team.zone')}</span>
          <select name="zone" className={cn('mt-1.5 cursor-pointer', field)}>
            <option value="">—</option>
            {['RECEPTION', 'INSPECTION', 'QUALITY', 'WAREHOUSE', 'PRODUCTION', 'LOGISTICS'].map(
              (zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="block">
          <span className="eyebrow">{t('team.service')}</span>
          <input name="service" className={cn('mt-1.5', field)} />
        </label>
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-2xs text-crit-soft">
          {error}
        </p>
      )}

      <p className="text-2xs text-ink-3">{t('team.roleGrantsCode')}</p>

      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn-primary">
          {t('common.save')}
        </button>
        <button type="button" onClick={onDone} className="btn-ghost">
          {t('common.cancel')}
        </button>
      </div>
    </form>
  )
}

export type { TeamMember }
