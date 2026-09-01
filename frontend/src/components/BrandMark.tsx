import { useState } from 'react'

import { TataEmblem, TataWordmark, TataWordmarkInline } from './TataMark'

/**
 * The plant's mark.
 *
 * Prefers the official file if it has been dropped into `public/brand/`, and
 * falls back to the drawn wordmark otherwise. That order matters: the real
 * asset is always better than a rebuild, and the rebuild only exists so the
 * screens are not empty on a machine where nobody has copied it yet.
 *
 * `inline` picks the one-line lockup for the rail, where height is the
 * constraint; the stacked one is for the entry screen, where it is not.
 */
export function BrandMark({
  className,
  inline = false,
}: {
  className?: string
  inline?: boolean
}) {
  const [missing, setMissing] = useState(false)

  if (missing) {
    return inline ? (
      <TataWordmarkInline className={className} />
    ) : (
      <TataWordmark className={className} />
    )
  }

  return (
    <img
      src="/brand/tata-advanced-systems.png"
      alt="Tata Advanced Systems"
      onError={() => setMissing(true)}
      className={className}
    />
  )
}

/**
 * The parent Tata mark - the oval and the wordmark under it.
 *
 * Same rule as `BrandMark`: the official file wins, the drawing is the
 * fallback. Kept separate because the two lockups are not interchangeable -
 * this one is square and belongs where a badge fits, not in a horizontal rail.
 */
export function BrandEmblem({ className }: { className?: string }) {
  const [missing, setMissing] = useState(false)

  if (missing) return <TataEmblem className={className} />

  return (
    <img
      src="/brand/tata.png"
      alt="Tata"
      onError={() => setMissing(true)}
      className={className}
    />
  )
}
