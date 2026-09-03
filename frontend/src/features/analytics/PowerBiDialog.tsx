/**
 * The Power BI hand-off.
 *
 * SLCC never depends on Power BI being connected: this dialog hands over the
 * report and the raw datasets, and stops there. What it does guarantee is that
 * a figure read in Power BI and the same figure read on this screen come from
 * one source - what is offered below is what the API serves, not a parallel
 * export.
 *
 * Two people open this, and they want opposite things. One wants the SLCC
 * report and nothing else; they get a download and are gone in a click. The
 * other is building their own model and needs the endpoint, the column names
 * and the DAX. The first used to have to read past the second's material to
 * find out a ready report existed - so the ready report leads, and the raw
 * material is one click away rather than in the way.
 */

import { ChevronDown, Copy, Check, Download, FileDown, Palette } from 'lucide-react'
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
  const [showRaw, setShowRaw] = useState(false)

  const endpoint = `${API_BASE_URL}/analytics/powerbi`
  const themeUrl = `${API_BASE_URL}/analytics/powerbi/theme.json`
  const reportUrl = `${API_BASE_URL}/analytics/powerbi/report.zip`

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
        {/* The ready report. It is the answer for almost everyone who opens
            this, so it gets the accent surface and the top of the dialog. */}
        <div className="rounded-xl border border-accent/30 bg-accent-dim p-4">
          <div className="flex flex-wrap items-start gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent/12 text-accent">
              <FileDown className="h-4 w-4" strokeWidth={1.9} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-ink">{t('powerbi.ready')}</p>
              {catalog.data ? (
                <p className="numeric mt-0.5 text-2xs text-accent">
                  {t('powerbi.readyContents', {
                    tables: catalog.data.datasets.length + 1,
                    measures: catalog.data.measures.length,
                  })}
                </p>
              ) : null}
              <p className="mt-1.5 text-2xs leading-relaxed text-ink-3">
                {t('powerbi.readyHint')}
              </p>
            </div>
            <a
              href={reportUrl}
              download="SLCC-PowerBI.zip"
              className="btn btn-primary h-9 shrink-0 px-4"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              {t('powerbi.download')}
            </a>
          </div>
          {/* Said here rather than discovered on a Monday: the file carries
              queries, not figures. Open it with the API down and it is empty,
              which is the honest failure - not last month's numbers. */}
          <p className="mt-3 border-t border-accent/20 pt-2.5 text-2xs leading-relaxed text-ink-3">
            {t('powerbi.readyEmpty')}
          </p>
        </div>

        <div className="rounded-xl border border-line">
          <button
            type="button"
            onClick={() => setShowRaw((value) => !value)}
            aria-expanded={showRaw}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-colors hover:bg-elevated/60"
          >
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-ink">{t('powerbi.build')}</p>
              <p className="mt-0.5 text-2xs leading-relaxed text-ink-3">
                {t('powerbi.buildHint')}
              </p>
            </div>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-ink-3 transition-transform duration-[var(--t-base)] ${
                showRaw ? 'rotate-180' : ''
              }`}
              aria-hidden="true"
            />
          </button>

          {showRaw ? (
            <div className="space-y-4 border-t border-line px-4 py-4">
              <div>
                <p className="eyebrow">{t('powerbi.endpoint')}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <code className="numeric min-w-0 flex-1 truncate rounded border border-line bg-panel px-2.5 py-1.5 text-2xs text-ink-2">
                    {endpoint}
                  </code>
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={
                      copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />
                    }
                    onClick={copyEndpoint}
                  >
                    {copied ? t('powerbi.copied') : t('powerbi.copy')}
                  </Button>
                </div>
                <p className="mt-2 text-2xs leading-relaxed text-ink-3">
                  {t('powerbi.howTo')}
                </p>
              </div>

              {/* A report that reads SLCC's figures in someone else's colours is
                  a second product. The theme is how the two stay one. */}
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-elevated/60 px-3 py-2.5">
                <Palette className="h-4 w-4 shrink-0 text-accent" strokeWidth={1.9} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-ink">{t('powerbi.theme')}</p>
                  <p className="mt-0.5 text-2xs leading-relaxed text-ink-3">
                    {t('powerbi.themeHint')}
                  </p>
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
                            <p className="numeric mt-1.5 text-[11px] leading-relaxed text-ink-3/80">
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
                          <code className="numeric mt-1 block overflow-x-auto whitespace-pre rounded border border-line bg-panel px-2 py-1.5 text-[11px] text-accent">
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
          ) : null}
        </div>
      </div>
    </Modal>
  )
}
