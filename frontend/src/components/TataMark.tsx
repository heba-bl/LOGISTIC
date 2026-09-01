/**
 * The Tata Advanced Systems wordmark, drawn.
 *
 * This is a recreation, not the official asset: an image cannot be copied out
 * of a conversation onto disk, so the choice was between a placeholder and a
 * close typographic rebuild. The rebuild wins because the mark is a wordmark -
 * "TATA" over "ADVANCED SYSTEMS" - and type is reproducible in a way a drawn
 * emblem is not.
 *
 * `BrandMark` still prefers the real file when one exists in `public/brand/`,
 * so dropping the official PNG in replaces this without touching any code. Use
 * the official file for anything that leaves the school.
 *
 * The oval T device from the parent Tata mark is deliberately NOT redrawn: its
 * curvature is the part nobody gets right by eye, and a subtly wrong emblem
 * looks worse than no emblem.
 */

const BLUE = '#1668B3'

export function TataWordmark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 96"
      className={className}
      role="img"
      aria-label="Tata Advanced Systems"
    >
      <text
        x="100"
        y="32"
        textAnchor="middle"
        fill={BLUE}
        style={{
          font: '800 34px Inter, "Segoe UI", system-ui, sans-serif',
          letterSpacing: '0.02em',
        }}
      >
        TATA
      </text>
      <text
        x="100"
        y="62"
        textAnchor="middle"
        fill={BLUE}
        style={{
          font: '700 25px Inter, "Segoe UI", system-ui, sans-serif',
          letterSpacing: '0.01em',
        }}
      >
        ADVANCED
      </text>
      <text
        x="100"
        y="88"
        textAnchor="middle"
        fill={BLUE}
        style={{
          font: '700 25px Inter, "Segoe UI", system-ui, sans-serif',
          letterSpacing: '0.01em',
        }}
      >
        SYSTEMS
      </text>
    </svg>
  )
}

/** The same wordmark set on one line, for a rail where height is the constraint. */
export function TataWordmarkInline({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 210 40"
      className={className}
      role="img"
      aria-label="Tata Advanced Systems"
    >
      <text
        x="0"
        y="17"
        fill={BLUE}
        style={{
          font: '800 20px Inter, "Segoe UI", system-ui, sans-serif',
          letterSpacing: '0.04em',
        }}
      >
        TATA
      </text>
      <text
        x="0"
        y="34"
        fill={BLUE}
        style={{
          font: '700 13px Inter, "Segoe UI", system-ui, sans-serif',
          letterSpacing: '0.06em',
        }}
      >
        ADVANCED SYSTEMS
      </text>
    </svg>
  )
}

/**
 * The Tata oval, approximated.
 *
 * The mark is one ellipse with two white wings cut out of its upper half; what
 * is left reads as a T. That construction is simple enough to rebuild honestly
 * - it is geometry, not lettering - but the exact curvature of the wings is
 * proprietary, so this is a likeness and not the asset.
 *
 * `BrandEmblem` prefers `public/brand/tata.png` whenever that file exists, and
 * for anything that leaves the school the official file is the one to use.
 */
export function TataEmblem({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} role="img" aria-label="Tata">
      <defs>
        <clipPath id="tata-oval">
          <ellipse cx="50" cy="35" rx="47" ry="33" />
        </clipPath>
      </defs>

      <ellipse cx="50" cy="35" rx="47" ry="33" fill={BLUE} />

      {/* The two wings. Their inner edges curve away from the stem, which is
          what stops the negative space reading as a plain cross. */}
      <g clipPath="url(#tata-oval)" fill="#FFFFFF">
        <path d="M -2 -2 H 45.5 V 26 Q 45.5 37 33 39 H -2 Z" />
        <path d="M 102 -2 H 54.5 V 26 Q 54.5 37 67 39 H 102 Z" />
      </g>

      {/* The wordmark under the oval, as the lockup has it. */}
      <text
        x="50"
        y="92"
        textAnchor="middle"
        fill={BLUE}
        style={{
          font: '800 30px Inter, "Segoe UI", system-ui, sans-serif',
          letterSpacing: '0.04em',
        }}
      >
        TATA
      </text>
    </svg>
  )
}
