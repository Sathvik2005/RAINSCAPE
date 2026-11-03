export interface ForecastInterval {
  interval_start_hour: number
  interval_end_hour: number
  valid_time: string
}

export interface ForecastMetadata {
  model: string
  product: string
  cycle: string
  parameter: string
  source_units: string
  display_units: 'mm'
  grid_type: string
  ni: number
  nj: number
  number_of_points: number
  grid_resolution_degrees: { longitude: number; latitude: number }
  steps: ForecastInterval[]
}

export interface SourceMetadata {
  model: string
  product: string
  cycle: string
  source_sha256: string
  baseline_source_sha256: string | null
  retrieved_at: string | null
  parameter_short_name: string
  parameter_name: string
  parameter_id: number
  source_units: string
  step_type: string
  statistical_processing: number | null
  accumulation_start_hour: number
  accumulation_end_hour: number
  interval_start_hour: number
  interval_end_hour: number
  valid_time: string
  grid_type: string
  ni: number
  nj: number
  number_of_points: number
  scanning_mode: number
  bitmap_present: boolean
  missing_count: number | null
  packing_error_source_units: number | null
  processing_version: string
}

export interface ForecastStep extends ForecastInterval {
  amount_mm: number | null
  below_encoding_resolution: boolean
  unit: 'mm'
  encoding_uncertainty_mm: number
  values_zeroed_as_indeterminate: number
  source: SourceMetadata
}

export interface PointForecast {
  model: string
  selected_location: { latitude: number; longitude: number }
  grid_cell: { latitude: number; longitude: number }
  sampling: 'nearest_grid_cell'
  interval_semantics: 'interval_amount'
  steps: ForecastStep[]
}

export interface RegionCell {
  latitude: number
  longitude: number
  amount_mm: number | null
  below_encoding_resolution: boolean
}

export interface RegionForecast {
  model: string
  interval_start_hour: number
  interval_end_hour: number
  valid_time: string
  unit: 'mm'
  source_units: string
  encoding_uncertainty_mm: number
  values_zeroed_as_indeterminate: number
  grid_type: string
  grid_resolution_degrees: { longitude: number; latitude: number }
  missing_value_semantics: 'null'
  cells: RegionCell[]
  source: SourceMetadata
}

export interface GeocodedPlace {
  id: number
  name: string
  latitude: number
  longitude: number
  country?: string
  country_code?: string
  admin1?: string
  admin2?: string
  timezone?: string
}

export interface Place {
  name: string
  latitude: number
  longitude: number
  country?: string
  admin1?: string
  countryCode?: string
}
