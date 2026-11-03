import * as L from 'leaflet'
import type { GeoJSON as LeafletGeoJSON, Map as LeafletMap, CircleMarker } from 'leaflet'
import { useEffect, useRef } from 'react'
import type { Feature, FeatureCollection, Point } from 'geojson'
import type { ForecastStep, Place, RegionCell, RegionForecast } from '../types/api'
import { formatUtc } from '../lib/forecastSummary'
import { PRECIPITATION_COLORS, precipitationColor } from '../lib/mapStyle'

interface Props {
  place: Place
  region: RegionForecast | null
  selectedStep: ForecastStep | null
  loading: boolean
  error: string | null
  onBoundsChange: (bounds: { west: number; south: number; east: number; north: number }) => void
  onCellSelect: (latitude: number, longitude: number) => void
}

interface CellProperties { amount_mm: number | null; below_encoding_resolution: boolean }
type CellFeature = Feature<Point, CellProperties>
const emptyCollection: FeatureCollection<Point, CellProperties> = { type: 'FeatureCollection', features: [] }

function normalizedLongitude(value: number) {
  return ((value + 180) % 360 + 360) % 360 - 180
}

function toFeatureCollection(cells: RegionCell[]): FeatureCollection<Point, CellProperties> {
  return {
    type: 'FeatureCollection',
    features: cells.map((cell): CellFeature => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [cell.longitude, cell.latitude] },
      properties: { amount_mm: cell.amount_mm, below_encoding_resolution: cell.below_encoding_resolution },
    })),
  }
}

export function ForecastMap({ place, region, selectedStep, loading, error, onBoundsChange, onCellSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<LeafletMap | null>(null)
  const gridRef = useRef<LeafletGeoJSON | null>(null)
  const selectedMarkerRef = useRef<CircleMarker | null>(null)
  const regionRef = useRef(region)
  const boundsHandlerRef = useRef(onBoundsChange)
  const cellHandlerRef = useRef(onCellSelect)
  regionRef.current = region
  boundsHandlerRef.current = onBoundsChange
  cellHandlerRef.current = onCellSelect

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, {
      center: [place.latitude, place.longitude],
      zoom: 6,
      minZoom: 3,
      maxZoom: 15,
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: true,
    })
    const tileUrl = import.meta.env.VITE_BASEMAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    L.tileLayer(tileUrl, {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)

    const canvasRenderer = L.canvas({ padding: 0.5 })
    const selectedMarker = L.circleMarker([place.latitude, place.longitude], {
      radius: 8, color: '#ffffff', weight: 3, fillColor: '#d16b56', fillOpacity: 1, interactive: false,
    }).addTo(map)
    const cellLayer = L.geoJSON(emptyCollection, {
      pointToLayer: (feature, latlng) => {
        const cell = feature.properties as CellProperties
        const marker = L.circleMarker(latlng, {
          radius: 7, color: '#ffffff', weight: 0.7,
          fillColor: precipitationColor(cell.amount_mm, cell.below_encoding_resolution), fillOpacity: 0.94,
          renderer: canvasRenderer,
        })
        return marker
      },
    }).addTo(map)
    const cellTooltip = L.tooltip({ sticky: true, opacity: 0.95 })
    cellLayer.on('click', (event: L.LeafletMouseEvent) => cellHandlerRef.current(event.latlng.lat, event.latlng.lng))
    cellLayer.on('mouseover', (event: L.LeafletMouseEvent & { layer?: L.Layer & { feature?: Feature<Point, CellProperties> } }) => {
      const cell = event.layer?.feature?.properties
      if (!cell) return
      const amount = cell.amount_mm === null ? 'No valid data' : `${cell.amount_mm.toFixed(3)} mm`
      const qualifier = cell.below_encoding_resolution ? ' · within packing uncertainty' : ''
      cellTooltip.setLatLng(event.latlng).setContent(`${amount}${qualifier}`).addTo(map)
    })
    cellLayer.on('mouseout', () => { if (map.hasLayer(cellTooltip)) map.removeLayer(cellTooltip) })

    let boundsTimer = 0
    const publishBounds = () => {
      window.clearTimeout(boundsTimer)
      boundsTimer = window.setTimeout(() => {
        const bounds = map.getBounds()
        boundsHandlerRef.current({
          west: Number(normalizedLongitude(bounds.getWest()).toFixed(3)),
          south: Number(Math.max(-90, bounds.getSouth()).toFixed(3)),
          east: Number(normalizedLongitude(bounds.getEast()).toFixed(3)),
          north: Number(Math.min(90, bounds.getNorth()).toFixed(3)),
        })
      }, 250)
    }

    map.on('moveend', publishBounds)
    map.whenReady(() => {
      if (regionRef.current) cellLayer.addData(toFeatureCollection(regionRef.current.cells))
      publishBounds()
    })
    mapRef.current = map
    gridRef.current = cellLayer
    selectedMarkerRef.current = selectedMarker

    return () => {
      window.clearTimeout(boundsTimer)
      map.remove()
      mapRef.current = null
      gridRef.current = null
      selectedMarkerRef.current = null
    }
    // Map construction is intentionally one-time; later position changes use flyTo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    selectedMarkerRef.current?.setLatLng([place.latitude, place.longitude])
    const map = mapRef.current
    if (map) map.flyTo([place.latitude, place.longitude], Math.max(map.getZoom(), 6), { duration: 0.5 })
  }, [place.latitude, place.longitude])

  useEffect(() => {
    const layer = gridRef.current
    if (!layer) return
    layer.clearLayers()
    if (region) layer.addData(toFeatureCollection(region.cells))
  }, [region])

  const interval = region
    ? `${region.interval_start_hour}–${region.interval_end_hour} h`
    : selectedStep ? `${selectedStep.interval_start_hour}–${selectedStep.interval_end_hour} h` : 'selected step'

  return (
    <div className="map-frame" aria-label="Precipitation forecast map">
      <div className="map-canvas" ref={containerRef} role="region" aria-label="Interactive map. Use arrow keys to pan and plus or minus to zoom." />
      <div className="map-corner-label">{selectedStep ? `IFS · ${selectedStep.interval_start_hour}–${selectedStep.interval_end_hour} h · ${formatUtc(selectedStep.valid_time)}` : 'IFS · interval precipitation'}</div>
      {loading && <div className="map-error" role="status">Updating cells for this view…</div>}
      {!loading && error && <div className="map-error" role="status">{error}</div>}
      <div className="map-legend" aria-label="Map legend">
        <div className="legend-heading"><span>Interval amount</span><span>mm · {interval}</span></div>
        <div className="legend-scale">
          {[
            ['0–0.1', PRECIPITATION_COLORS.zero], ['0.1–0.5', PRECIPITATION_COLORS.trace],
            ['0.5–2', PRECIPITATION_COLORS.light], ['2–5', PRECIPITATION_COLORS.moderate],
            ['5–15', PRECIPITATION_COLORS.heavy], ['15+', PRECIPITATION_COLORS.veryHeavy],
          ].map(([label, color]) => <span className="legend-chip" key={label}><i className="legend-swatch" style={{ backgroundColor: color }} />{label}</span>)}
        </div>
        <div className="legend-foot"><span>▰ Missing</span> · <span style={{ color: '#806c4d' }}>▰ Below encoding resolution</span></div>
      </div>
    </div>
  )
}
