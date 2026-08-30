/**
 * The SLCC visualisation library.
 *
 * One system, not several: every chart here is hand-drawn SVG over the same
 * design tokens, so a mark inherits the theme, the locale and the state palette
 * for free. That is why no charting dependency was added - a second library
 * would mean a second set of colours, a second tooltip and a second dark mode
 * to keep in step.
 *
 * Each form is used only where it answers a question the others cannot:
 *
 *   AnalyticsBarChart      compare categories
 *   AnalyticsColumnPairs   two measures per subject, columns side by side
 *   AnalyticsStockDemand   does this reference cover its demand
 *   AnalyticsStackedBar    composition of one whole
 *   AnalyticsHistogram     where the tail sits, not just the average
 *   AnalyticsPie           share of a whole, few slices
 *   AnalyticsDonut         share of a whole, with a headline in the middle
 *   AnalyticsLineChart     how a level moved
 *   AnalyticsAreaChart     the same, when volume matters
 *   AnalyticsComboChart    two measures of the same unit, one axis
 *   AnalyticsWaterfall     why a balance ended where it did
 *   AnalyticsTreemap       what the bulk is made of
 *   AnalyticsHeatmap       which cell is under pressure
 *   AnalyticsMatrix        a reference against the zones holding it
 *   AnalyticsScatter       two dimensions at once, to spot the outlier
 *   AnalyticsGauge         a measure against a target
 *   WarehouseMap           the racks as a plan
 *   KpiCard                a figure that needs no chart
 */

export { ChartCard, ChartEmpty, ChartTooltip, Legend, RiskChip, useUnitLabel } from './primitives'
export { KpiCard } from './KpiCard'
export { SelectionDetail } from './SelectionDetail'

export { AnalyticsColumnPairs } from './columns'

export {
  HBarChart as AnalyticsBarChart,
  StockDemandBars as AnalyticsStockDemand,
  StackedBar as AnalyticsStackedBar,
} from './bars'

export { DonutChart as AnalyticsDonut, Gauge as AnalyticsGauge, AnalyticsPie } from './circular'

export {
  ComboChart as AnalyticsComboChart,
  Waterfall as AnalyticsWaterfall,
  Heatmap as AnalyticsHeatmap,
  ScatterPlot as AnalyticsScatter,
} from './series'

export {
  AnalyticsAreaChart,
  AnalyticsHistogram,
  AnalyticsLineChart,
  AnalyticsScatterXY,
  AnalyticsTreemap,
} from './plots'

export { AnalyticsMatrix, WarehouseMap } from './layout'

export { DecisionList, FlowFunnel, PriorityTable, ZoneOccupancy } from './decision'
