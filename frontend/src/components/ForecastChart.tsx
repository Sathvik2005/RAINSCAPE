import { formatStepValue } from '../lib/forecastSummary'
import type { ForecastStep } from '../types/api'

interface Props {
  steps: ForecastStep[]
  selectedEndStep: number
  onSelect: (step: ForecastStep) => void
}

export function ForecastChart({ steps, selectedEndStep, onSelect }: Props) {
  const maxValue = Math.max(0.1, ...steps.flatMap((step) => step.amount_mm === null ? [] : [step.amount_mm]))
  const maxEnd = Math.max(1, ...steps.map((step) => step.interval_end_hour))
  const baseline = 96
  const chartHeight = 75
  const barWidth = Math.max(12, Math.min(28, 232 / Math.max(steps.length, 1)))
  const bars = steps.map((step) => {
    const midpoint = (step.interval_start_hour + step.interval_end_hour) / 2
    const x = 28 + (midpoint / maxEnd) * 264
    const value = step.amount_mm ?? 0
    const height = step.amount_mm === null ? 0 : Math.max(value > 0 ? 2 : 1, (value / maxValue) * chartHeight)
    return { step, x, y: baseline - height, height }
  })

  return (
    <div>
      <div className="chart-wrap">
        <svg className="forecast-chart" viewBox="0 0 320 112" role="img" aria-label={`Interval precipitation amounts: ${steps.map((step) => `${step.interval_start_hour} to ${step.interval_end_hour} hours, ${step.amount_mm === null ? 'missing data' : formatStepValue(step)}`).join('; ')}`}>
          <title>Forecast precipitation by accumulation interval, in millimetres</title>
          {[21, 46, 71, 96].map((y) => <line key={y} className="chart-gridline" x1="18" x2="302" y1={y} y2={y} />)}
          <text x="0" y="24" className="chart-axis-label">{maxValue.toFixed(1)}</text>
          <text x="0" y="98" className="chart-axis-label">0</text>
          {bars.map(({ step, x, y, height }) => {
            const selected = step.interval_end_hour === selectedEndStep
            const fill = step.below_encoding_resolution ? '#d6c7aa' : selected ? '#d37951' : '#42a194'
            return step.amount_mm === null ? (
              <g key={step.interval_end_hour}>
                <line x1={x - barWidth / 2} x2={x + barWidth / 2} y1={baseline} y2={baseline} stroke="#9aa7a2" strokeDasharray="3 3" strokeWidth="3" />
                <title>{`${step.interval_start_hour}–${step.interval_end_hour} h: missing value`}</title>
              </g>
            ) : (
              <g key={step.interval_end_hour}>
                <rect x={x - barWidth / 2} y={y} width={barWidth} height={height} rx="3" fill={fill} opacity={selected ? 1 : .78} />
                <title>{`${step.interval_start_hour}–${step.interval_end_hour} h: ${formatStepValue(step)}${step.below_encoding_resolution ? ', within encoding uncertainty' : ''}`}</title>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="chart-labels" role="group" aria-label="Forecast interval selection">
        {steps.map((step) => (
          <button
            className="chart-step" key={step.interval_end_hour} type="button"
            aria-pressed={step.interval_end_hour === selectedEndStep}
            aria-label={`Show ${step.interval_start_hour} to ${step.interval_end_hour} hour interval, ${formatStepValue(step)}`}
            style={{ flexGrow: step.interval_end_hour - step.interval_start_hour, flexBasis: 0 }}
            onClick={() => onSelect(step)}
          >
            <strong>{step.interval_end_hour.toString().padStart(2, '0')}Z</strong>
            <span>{formatStepValue(step)}</span>
            <small>{step.interval_start_hour}–{step.interval_end_hour} h</small>
          </button>
        ))}
      </div>
    </div>
  )
}
