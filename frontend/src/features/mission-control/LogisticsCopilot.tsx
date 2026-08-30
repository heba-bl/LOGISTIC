import { useEffect, useRef, useState, type FormEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CornerDownLeft, Loader2, Sparkles, User2 } from 'lucide-react'

import { aiApi } from '@/services/slcc.service'
import { toErrorMessage } from '@/services/apiClient'
import { cn } from '@/utils/cn'
import type { CopilotAnswer } from '@/types/domain'

interface Exchange {
  id: number
  question: string
  answer: CopilotAnswer | null
  error?: string
}

const FALLBACK_SUGGESTIONS = [
  "What are today's priorities?",
  'Which lots are blocked?',
  'Is there a shortage risk?',
]

let exchangeId = 1

/**
 * Logistics Copilot.
 *
 * Questions are answered by the backend from live data - every figure shown
 * comes with the source that produced it. The Copilot never invents a number.
 */
export function LogisticsCopilot({ compact = false }: { compact?: boolean }) {
  const [question, setQuestion] = useState('')
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>(FALLBACK_SUGGESTIONS)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    aiApi
      .suggestions()
      .then((list) => setSuggestions(list.slice(0, compact ? 3 : 6)))
      .catch(() => setSuggestions(FALLBACK_SUGGESTIONS))
  }, [compact])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [exchanges])

  async function ask(value: string) {
    const trimmed = value.trim()
    if (!trimmed || loading) return

    const id = exchangeId++
    setExchanges((current) => [...current, { id, question: trimmed, answer: null }])
    setQuestion('')
    setLoading(true)

    try {
      const answer = await aiApi.copilot(trimmed)
      setExchanges((current) =>
        current.map((item) => (item.id === id ? { ...item, answer } : item)),
      )
    } catch (error) {
      setExchanges((current) =>
        current.map((item) =>
          item.id === id ? { ...item, error: toErrorMessage(error) } : item,
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void ask(question)
  }

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-40" aria-hidden="true">
        <div className="absolute inset-y-0 w-1/4 animate-scan bg-gradient-to-r from-transparent via-accent/10 to-transparent" />
      </div>

      {/* Conversation */}
      {exchanges.length > 0 && (
        <div
          ref={scrollRef}
          className={cn(
            'relative space-y-3 overflow-y-auto border-b border-line px-5 py-4',
            compact ? 'max-h-64' : 'max-h-96',
          )}
        >
          <AnimatePresence initial={false}>
            {exchanges.map((exchange) => (
              <motion.div
                key={exchange.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-2"
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded border border-line bg-elevated">
                    <User2 className="h-3 w-3 text-ink-3" />
                  </span>
                  <p className="text-xs font-medium text-ink">{exchange.question}</p>
                </div>

                <div className="flex items-start gap-2">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded border border-accent/30 bg-accent-dim">
                    {exchange.answer || exchange.error ? (
                      <Sparkles className="h-3 w-3 text-accent" />
                    ) : (
                      <Loader2 className="h-3 w-3 animate-spin text-accent" />
                    )}
                  </span>

                  <div className="min-w-0 flex-1">
                    {exchange.error ? (
                      <p className="text-xs text-crit-soft">{exchange.error}</p>
                    ) : exchange.answer ? (
                      <>
                        <p className="whitespace-pre-line text-xs leading-relaxed text-ink-2">
                          {exchange.answer.answer}
                        </p>
                        {exchange.answer.sources.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {exchange.answer.sources.map((source) => (
                              <span
                                key={source.label}
                                className="rounded border border-line bg-elevated px-2 py-0.5 text-[10px] text-ink-3"
                              >
                                {source.label}:{' '}
                                <span className="numeric text-ink-2">{source.value}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-xs text-ink-3">Analysing the data…</p>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Composer */}
      <div className="relative flex flex-col gap-4 p-5 lg:flex-row lg:items-center">
        <div className="flex items-center gap-3">
          <motion.span
            animate={{ scale: [1, 1.06, 1] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-accent/30 bg-accent-dim"
          >
            <Sparkles className="h-4 w-4 text-accent" strokeWidth={1.9} />
          </motion.span>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-ink">Logistics Copilot</p>
            <p className="mt-1 text-2xs text-ink-3">Answers grounded in live data.</p>
          </div>
        </div>

        <div className="flex-1">
          <form onSubmit={onSubmit} className="relative">
            <input
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask Logistics Copilot…"
              aria-label="Ask Logistics Copilot"
              className="w-full rounded-lg border border-line bg-panel/80 py-2.5 pl-4 pr-24 text-xs text-ink placeholder:text-ink-3 transition-colors hover:border-line-strong focus:border-accent/60 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded border border-line bg-elevated px-2 py-1 text-[9px] font-medium text-ink-2 transition-colors hover:border-accent/50 hover:text-accent disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-2.5 w-2.5 animate-spin" />
              ) : (
                <CornerDownLeft className="h-2.5 w-2.5" />
              )}
              Ask
            </button>
          </form>

          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => void ask(suggestion)}
                disabled={loading}
                className="rounded-full border border-line bg-panel/60 px-2.5 py-1 text-[10px] text-ink-3 transition-colors hover:border-accent/40 hover:text-accent disabled:opacity-50"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
