import { useState } from 'react'
import { Monitor, Moon, Save, Settings as SettingsIcon, Sun, Users } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  ErrorPanel,
  Input,
  LoadingPanel,
  Panel,
  StatusDot,
} from '@/components/ui'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useTheme, type ThemeChoice } from '@/hooks/useTheme'
import { useI18n } from '@/i18n/I18nProvider'
import type { Locale } from '@/i18n/messages'
import { toErrorMessage } from '@/services/apiClient'
import { catalogApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import type { Setting } from '@/types/domain'

const GROUP_LABELS: Record<string, string> = {
  reception: 'Reception tolerance',
  inspection: 'Sampling and defects',
  warehouse: 'Warehouse thresholds',
  ai: 'AI thresholds',
  general: 'General',
}

/**
 * Settings.
 *
 * Business thresholds live in the database, not in the code: the 5% reception
 * tolerance, the sampling rate, the defect threshold and the saturation levels
 * are all editable here and take effect immediately.
 */
export default function Settings() {
  const { t, ts } = useI18n()
  const settings = useApiResource(() => catalogApi.settings(), [])
  const parts = useApiResource(() => catalogApi.parts(), [])
  const suppliers = useApiResource(() => catalogApi.suppliers(), [])

  const groups = (settings.data ?? []).reduce<Record<string, Setting[]>>((acc, setting) => {
    acc[setting.group] = [...(acc[setting.group] ?? []), setting]
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <PageHeader title={t('settings.title')} description={t('settings.subtitle')} />

      <AppearancePanel />
      <OperatorPanel />

      <Panel
        title={t('settings.businessRules')}
        subtitle={t('settings.businessRulesSubtitle')}
        bodyClassName=""
        action={<SettingsIcon className="h-3.5 w-3.5 text-ink-3" />}
      >
        {settings.initialLoading ? (
          <LoadingPanel rows={5} />
        ) : settings.error ? (
          <ErrorPanel message={settings.error} onRetry={settings.refresh} />
        ) : (
          <div className="divide-y divide-line">
            {Object.entries(groups).map(([group, rows]) => (
              <div key={group} className="px-5 py-4">
                <p className="eyebrow mb-3">{GROUP_LABELS[group] ?? ts(group)}</p>
                <ul className="space-y-3">
                  {rows.map((setting) => (
                    <SettingRow
                      key={setting.id}
                      setting={setting}
                      onSaved={() => void settings.refresh()}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel
          title={t('settings.parts')}
          subtitle={`${parts.data?.length ?? 0} references — tolerance class per part`}
          bodyClassName=""
        >
          {parts.initialLoading ? (
            <LoadingPanel rows={4} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-line">
                    <th className="eyebrow px-5 py-2.5 font-semibold">Reference</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Class</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">Tolerance</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">Safety</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">Daily use</th>
                  </tr>
                </thead>
                <tbody>
                  {parts.data?.map((part) => (
                    <tr key={part.id} className="border-b border-line/60 last:border-0">
                      <td className="px-5 py-2.5">
                        <span className="numeric text-xs text-ink">{part.reference}</span>
                        <span className="block truncate text-2xs text-ink-3">
                          {part.designation}
                        </span>
                      </td>
                      <td className="px-5 py-2.5">
                        <Badge severity={part.size_class === 'LARGE' ? 'warn' : 'info'}>
                          {part.size_class === 'LARGE' ? 'Large' : 'Small'}
                        </Badge>
                      </td>
                      <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-2">
                        {part.reception_tolerance_percent !== null
                          ? `${part.reception_tolerance_percent}% (override)`
                          : part.size_class === 'LARGE'
                            ? 'exact'
                            : 'default'}
                      </td>
                      <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-2">
                        {part.safety_stock}
                      </td>
                      <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-2">
                        {part.average_daily_consumption}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel
          title={t('settings.suppliers')}
          subtitle={`${suppliers.data?.length ?? 0} active suppliers`}
          bodyClassName=""
        >
          {suppliers.initialLoading ? (
            <LoadingPanel rows={4} />
          ) : (
            <ul className="divide-y divide-line">
              {suppliers.data?.map((supplier) => (
                <li key={supplier.id} className="flex items-center gap-3 px-5 py-3">
                  <span className="numeric text-xs text-ink-2">{supplier.code}</span>
                  <span className="text-xs text-ink">{supplier.name}</span>
                  <span className="ml-auto text-2xs text-ink-3">
                    {supplier.country} · {supplier.lead_time_days} d lead time
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}

function SettingRow({ setting, onSaved }: { setting: Setting; onSaved: () => void }) {
  const [value, setValue] = useState(setting.value)
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  const dirty = value !== setting.value

  async function save() {
    setSaving(true)
    try {
      await catalogApi.updateSetting(setting.key, value)
      toast.success('Setting updated', `${setting.label} = ${value}`)
      onSaved()
    } catch (error) {
      toast.error('Update refused', toErrorMessage(error))
      setValue(setting.value)
    } finally {
      setSaving(false)
    }
  }

  return (
    <li className="flex flex-wrap items-start gap-3">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-ink">{setting.label}</p>
        {setting.description && (
          <p className="mt-0.5 text-2xs leading-relaxed text-ink-3">{setting.description}</p>
        )}
        <p className="numeric mt-1 text-[10px] text-ink-3/70">{setting.key}</p>
      </div>

      <div className="flex items-center gap-2">
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className={cn('numeric w-28 text-right', dirty && 'border-accent/50')}
        />
        <Button
          size="sm"
          variant={dirty ? 'primary' : 'secondary'}
          disabled={!dirty}
          loading={saving}
          icon={<Save className="h-3 w-3" />}
          onClick={() => void save()}
        >
          Save
        </Button>
      </div>
    </li>
  )
}

/** Theme and language. Both choices are persisted in the browser. */
function AppearancePanel() {
  const { t } = useI18n()
  const { choice, setChoice } = useTheme()
  const { locale, setLocale } = useI18n()

  const themes: { value: ThemeChoice; icon: typeof Sun; label: string }[] = [
    { value: 'light', icon: Sun, label: t('settings.themeLight') },
    { value: 'dark', icon: Moon, label: t('settings.themeDark') },
    { value: 'system', icon: Monitor, label: t('settings.themeSystem') },
  ]

  return (
    <Panel title={t('settings.appearance')} subtitle={t('settings.appearanceSubtitle')}>
      <div className="flex flex-wrap gap-8">
        <div>
          <p className="eyebrow mb-2">{t('topbar.theme')}</p>
          <div className="flex gap-2">
            {themes.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setChoice(option.value)}
                className={cn(
                  'flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium transition-colors',
                  choice === option.value
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-line text-ink-2 hover:bg-elevated hover:text-ink',
                )}
              >
                <option.icon className="h-3.5 w-3.5" />
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="eyebrow mb-2">{t('topbar.language')}</p>
          <div className="flex gap-2">
            {(['fr', 'en'] as Locale[]).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setLocale(code)}
                className={cn(
                  'rounded-md border px-4 py-2 text-xs font-semibold uppercase transition-colors',
                  locale === code
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-line text-ink-2 hover:bg-elevated hover:text-ink',
                )}
              >
                {code === 'fr' ? 'Francais' : 'English'}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  )
}

/** Simulated identity picker: roles are simulated, actions are attributed. */
function OperatorPanel() {
  const { t } = useI18n()
  const { users, actor, setActor, loading } = useActor()

  return (
    <Panel
      title={t('settings.actingAs')}
      subtitle={t('settings.actingAsSubtitle')}
      action={<Users className="h-3.5 w-3.5 text-ink-3" />}
    >
      {loading ? (
        <LoadingPanel rows={2} />
      ) : (
        <div className="flex flex-wrap gap-2">
          {users.map((user) => {
            const active = actor?.id === user.id
            return (
              <button
                key={user.id}
                type="button"
                onClick={() => setActor(user)}
                className={cn(
                  'flex items-center gap-2.5 rounded-lg border px-3 py-2 text-left transition-colors',
                  active
                    ? 'border-accent/50 bg-accent-dim'
                    : 'border-line bg-elevated hover:border-line-strong',
                )}
              >
                <StatusDot severity={active ? 'ok' : 'info'} />
                <span className="min-w-0">
                  <span className="numeric block text-2xs font-semibold text-accent/90">
                    {user.employee_number}
                  </span>
                  <span className="block text-xs font-medium text-ink">{user.full_name}</span>
                  <span className="block text-2xs text-ink-3">
                    {user.role?.label ?? 'No role'}
                    {user.service ? ` · ${user.service}` : ''}
                    {user.role?.can_validate ? ` · ${t('settings.canValidate')}` : ''}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
