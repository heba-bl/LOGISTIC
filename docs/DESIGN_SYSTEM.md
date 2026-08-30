# Design System — Industrial Control Center

The interface is a supervision console, not a generic admin dashboard. It is
read at a distance, often in a workshop environment: high contrast, dense
information, restrained motion.

## Surfaces

| Token | Hex | Usage |
|-------|-----|-------|
| `base` | `#070C14` | application background |
| `panel` | `#0C1524` | panel surface |
| `elevated` | `#111C2F` | cards inside a panel, hover state |
| `line` | `#1C2942` | separators, borders |
| `line-strong` | `#26375A` | emphasised border, hover |

A very low-opacity grid texture runs behind the content area to give the
"control room" feel without competing with data.

## Ink

| Token | Hex | Usage |
|-------|-----|-------|
| `ink` | `#E8EFF9` | values, titles |
| `ink-2` | `#94A6C0` | secondary text |
| `ink-3` | `#61748F` | labels, captions, units |

**Text always wears an ink token.** A number is never coloured by its status —
the coloured dot, badge or rail next to it carries the state. This keeps the
numeric column readable and stops colour from becoming noise.

## Functional colours

Reserved for state. Never used decoratively, never as a series colour.

| Meaning | Token | Hex | Used for |
|---------|-------|-----|----------|
| Normal / validated | `ok` | `#22C55E` | validated lots, stored stock, healthy API |
| Attention | `warn` | `#F59E0B` | pending decisions, thresholds approached |
| Critical / blocked | `crit` | `#EF4444` | blocked lots, stock below requirement |
| Information / movement | `info` | `#3B82F6` | in-transit, in-inspection, neutral events |

Accent `#38BDF8` is the interactive/brand colour (active nav, focus ring, flow
pulse) and is deliberately distinct from the four status colours.

### Rule: colour is never the only signal

Every status carries an icon **and** a text label (`CRITICAL`, `Pending
quality`, `Blocked`). A colourblind operator, a monochrome print or a glare-hit
screen still reads the state correctly.

## Typography

- **Inter** for the interface.
- **JetBrains Mono** (`.numeric`, tabular figures) for every quantity, lot
  number, timestamp and identifier — figures line up column to column.
- `.eyebrow`: 11px, uppercase, wide tracking, `ink-3` — section and column labels.

## Components

| Component | Role |
|-----------|------|
| `Panel` | the standard bordered surface; optional header with eyebrow title |
| `StatusDot` | 8px functional dot, optional radar pulse for live/critical |
| `Badge` | status pill — border + tint + uppercase label |
| `Meter` | single-track magnitude bar (occupancy, load) |

## Motion

Discreet, functional, never decorative-for-its-own-sake:

- **Entry**: 12px rise + fade, 0.4s, `cubic-bezier(0.22, 1, 0.36, 1)`,
  staggered ~50–80ms across a row.
- **Route change**: 8px cross-fade via `AnimatePresence mode="wait"`.
- **Active nav**: shared `layoutId` spring — the highlight travels between items.
- **Flow pulse**: a light particle crosses each connector, offset per stage, so
  the pipeline reads as *flowing* rather than static.
- **Live/critical states**: slow expanding ring on the status dot.

Nothing bounces, nothing spins, nothing loops fast enough to distract from a
number.

## Layout

- Sidebar 248px, fixed; content max-width 1600px.
- 4px base spacing scale, 16px gutters between panels.
- Mission Control vertical rhythm: KPI row → full-width flow → lots + alerts →
  activity + copilot. The six-stage flow always owns a full-width row so no
  stage is ever clipped.
