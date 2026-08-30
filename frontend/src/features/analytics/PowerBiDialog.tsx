/**
 * The Power BI hand-off.
 *
 * SLCC never depends on Power BI being connected: this dialog exposes the flat
 * datasets, the DAX measures and the report theme, and stops there. What it
 * does guarantee is that a figure read in Power BI and the same figure read on
 * this screen come from one source - the datasets below are the ones the API
 * serves, not a parallel export.
 */

import { Check, Copy, Download, Palette } from 'lucide-react'
import { useState } from 'react'

import { Button, ErrorPanel, LoadingPanel, Modal } from '@/components/ui'
import { useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { API_BASE_URL } from '@/services/apiClient'
import { analyticsApi } from '@/services/slcc.service'

export function PowerBiDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, formatNumber } = useI18n()
  const toast = useToast()
  const catalog = useApiResource(() => analyticsApi.powerbi(), [open], { enabled: open })
  const [copied, setCopied] = useState(false)

  const endpoint = `${API_BASE_URL}/analytics/powerbi`
  const themeUrl = `${API_BASE_URL}/analytics/powerbi/theme.json`

  function copyEndpoint() {
    void navigator.clipboard
      .writeText(endpoint)
      .then(() => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 2000)
      })
      .catch(() => toast.error(t('powerbi.copyFailed')))
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('powerbi.title')}
      subtitle={t('powerbi.subtitle')}
      width="lg"
      footer={
        <Button variant="ghost" onClick={onClose}>
          {t('common.close')}
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="rounded-lg border border-line bg-elevated/60 p-4">
          <p className="eyebrow">{t('powerbi.endpoint')}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <code className="numeric min-w-0 flex-1 truncate rounded border border-line bg-panel px-2.5 py-1.5 text-2xs text-ink-2">
              {endpoint}
            </code>
            <Button
              size="sm"
              variant="secondary"
              icon={copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              onClick={copyEndpoint}
            >
              {copied ? t('powerbi.copied') : t('powerbi.copy')}
            </Button>
          </div>
          <p className="mt-2 text-2xs leading-relaxed text-ink-3">{t('powerbi.howTo')}</p>
        </div>

        {/* The report must look like the application, so the theme travels with it. */}
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-accent/25 bg-accent-dim px-4 py-3">
          <Palette className="h-4 w-4 shrink-0 text-accent" strokeWidth={1.9} />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-ink">{t('powerbi.theme')}</p>
            <p className="mt-0.5 text-2xs leading-relaxed text-ink-3">{t('powerbi.themeHint')}</p>
          </div>
          <a
            href={themeUrl}
            download="SLCC.json"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-accent/40 px-2.5 py-1.5 text-2xs font-medium text-accent transition-colors hover:border-accent"
          >
            <Download className="h-3 w-3" />
            {t('common.download')}
          </a>
        </div>

        {catalog.initialLoading ? (
          <LoadingPanel rows={4} />
        ) : catalog.error ? (
          <ErrorPanel message={catalog.error} onRetry={catalog.refresh} />
        ) : catalog.data ? (
          <>
            <div>
              <p className="eyebrow mb-2">
                {t('powerbi.datasets', { count: catalog.data.datasets.length })}
              </p>
              <ul className="space-y-2">
                {catalog.data.datasets.map((dataset) => (
                  <li
                    key={dataset.name}
                    className="rounded-lg border border-line bg-elevated/60 px-3 py-2.5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="numeric text-xs font-semibold text-ink">
                        {dataset.name}
                      </span>
                      <span className="numeric ml-auto text-2xs text-ink-3">
                        {t('powerbi.shape', {
                          rows: formatNumber(dataset.rows.length),
                          columns: dataset.columns.length,
                        })}
                      </span>
                    </div>
                    <p className="mt-1 text-2xs text-ink-3">{dataset.description}</p>
                    {dataset.columns.length > 0 && (
                      <p className="numeric mt-1.5 text-[10px] leading-relaxed text-ink-3/80">
                        {dataset.columns.join(' · ')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="eyebrow mb-2">{t('powerbi.measures')}</p>
              <ul className="space-y-2">
                {catalog.data.measures.map((measure) => (
                  <li
                    key={measure.name}
                    className="rounded-lg border border-line bg-elevated/60 px-3 py-2.5"
                  >
                    <p className="text-xs font-medium text-ink">{measure.name}</p>
                    <code className="numeric mt-1 block overflow-x-auto whitespace-pre rounded border border-line bg-panel px-2 py-1.5 text-[10px] text-accent">
                      {measure.expression}
                    </code>
                    <p className="mt-1 text-2xs text-ink-3">{measure.description}</p>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  )
}
