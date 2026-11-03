export const PRECIPITATION_COLORS = {
  zero: '#e8f6f4',
  trace: '#b8e5dd',
  light: '#78cabe',
  moderate: '#42a194',
  heavy: '#27756e',
  veryHeavy: '#835c95',
  missing: '#aeb9b5',
  indeterminate: '#d6c7aa',
}

export function precipitationColor(amountMm: number | null, belowEncodingResolution: boolean) {
  if (amountMm === null) return PRECIPITATION_COLORS.missing
  if (belowEncodingResolution) return PRECIPITATION_COLORS.indeterminate
  if (amountMm >= 15) return PRECIPITATION_COLORS.veryHeavy
  if (amountMm >= 5) return PRECIPITATION_COLORS.heavy
  if (amountMm >= 2) return PRECIPITATION_COLORS.moderate
  if (amountMm >= 0.5) return PRECIPITATION_COLORS.light
  if (amountMm >= 0.1) return PRECIPITATION_COLORS.trace
  return PRECIPITATION_COLORS.zero
}
