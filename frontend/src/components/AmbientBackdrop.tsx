/**
 * The room behind the screens.
 *
 * A dashboard on a flat fill reads as a document. What separates a control
 * room from a spreadsheet is that the surface behind the data is not dead: it
 * has depth, and it moves slowly enough that you never catch it moving.
 *
 * Two drifting pools of light and a faint survey grid, both in the palette,
 * both far below any text. Nothing here carries meaning - it is the ground the
 * meaning sits on, which is exactly why it must never be bright enough to
 * compete with a status colour.
 *
 * It sits in the layout shell and not in the scrolling pane: a background
 * that travels with a long report turns into a parallax trick, and this is a
 * room, not an effect.
 */
export function AmbientBackdrop() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {/* The survey grid. 4% is deliberately at the edge of visible: you should
          register that the surface has a texture, not be able to count lines. */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgb(var(--c-ink)) 1px, transparent 1px),' +
            'linear-gradient(to bottom, rgb(var(--c-ink)) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(80rem 50rem at 50% 0%, black, transparent 75%)',
          WebkitMaskImage: 'radial-gradient(80rem 50rem at 50% 0%, black, transparent 75%)',
        }}
      />

      {/* Two pools of light on very long, mismatched cycles, so the pair never
          settles into a loop the eye can learn. */}
      <div
        className="ambient-drift absolute -left-[10%] top-[-20%] h-[46rem] w-[46rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(closest-side, rgb(var(--c-accent) / 0.16), transparent)' }}
      />
      <div
        className="ambient-drift-slow absolute -right-[15%] top-[10%] h-[38rem] w-[38rem] rounded-full blur-3xl"
        style={{ background: 'radial-gradient(closest-side, rgb(var(--c-chart-4) / 0.12), transparent)' }}
      />
    </div>
  )
}
