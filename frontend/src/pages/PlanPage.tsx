import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CloudRain, IndianRupee, MapPinned, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button, ErrorState, LoadingState, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { formatMoney } from '../lib/format'
import { usePlaces, useTrip } from '../lib/queries'
import { queryKeys } from '../lib/queryKeys'
import type { Place, PlanningAnalysis } from '../lib/types'

export function PlanPage() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const trip = useTrip(id)
  const places = usePlaces(id)
  const [selection, setSelection] = useState<Set<string>>(new Set())
  const [saved, setSaved] = useState(false)
  const analysis = useMutation({
    mutationFn: () => api.post<PlanningAnalysis>(`/trips/${id}/analyze`),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.analysis(id), result)
      queryClient.setQueryData(queryKeys.places(id), result.places)
      queryClient.invalidateQueries({ queryKey: queryKeys.trip(id) })
      setSelection(new Set(result.places.filter((place) => place.selected).map((place) => place.id)))
    },
  })
  const save = useMutation({
    mutationFn: (placeIds: string[]) => api.post<Place[]>(`/trips/${id}/places/select`, { place_ids: placeIds }),
    onSuccess: (result) => { queryClient.setQueryData(queryKeys.places(id), result); setSaved(true) },
  })
  const available = useMemo(() => analysis.data?.places ?? places.data ?? [], [analysis.data?.places, places.data])
  const selectedCount = useMemo(() => available.filter((place) => selection.has(place.id) || (place.selected && !selection.size)).length, [available, selection])
  if (trip.isLoading || places.isLoading) return <LoadingState label="Checking the map…" />
  if (trip.isError || !trip.data) return <ErrorState error={trip.error} retry={() => trip.refetch()} />
  const tripData = trip.data
  const toggle = (placeId: string) => setSelection((current) => {
    const base = current.size ? new Set(current) : new Set(available.filter((place) => place.selected).map((place) => place.id))
    if (base.has(placeId)) base.delete(placeId)
    else base.add(placeId)
    return base
  })
  return (
    <>
      <PageHeader title="Shape the route" intro="Weather and costs set the guardrails. You choose the places worth the time." action={<Button className="secondary" onClick={() => analysis.mutate()} disabled={analysis.isPending}>{analysis.isPending ? 'Analyzing…' : available.length ? 'Refresh analysis' : 'Analyze trip'}</Button>} />
      {analysis.isError && <ErrorState error={analysis.error} />}
      <section className="plan-metrics">
        <article><CloudRain /><span>Weather fit</span><strong>{tripData.weather_score ? `${tripData.weather_score}/10` : 'Pending'}</strong><p>{tripData.weather_summary ?? 'Analyze your dates for a seasonal read.'}</p></article>
        <article><IndianRupee /><span>Typical budget</span><strong>{tripData.estimated_cost ? formatMoney(tripData.estimated_cost, tripData.base_currency) : 'Pending'}</strong><p>{tripData.estimated_cost_min ? `${formatMoney(tripData.estimated_cost_min, tripData.base_currency)} – ${formatMoney(tripData.estimated_cost_max, tripData.base_currency)}` : 'Based on duration, group, and travel style.'}</p></article>
      </section>
      {available.length > 0 ? <section className="places-section">
        <div className="section-heading"><div><MapPinned /><h2>Recommended stops</h2></div><span>{selectedCount} selected</span></div>
        <div className="place-grid">{available.map((place) => {
          const checked = selection.size ? selection.has(place.id) : place.selected
          return <label className={`place-card ${checked ? 'selected' : ''}`} key={place.id}>
            <input type="checkbox" checked={checked} onChange={() => toggle(place.id)} aria-label={`Select ${place.name}`} />
            <div className="place-score">{place.relevance_score}</div><h3>{place.name}</h3><p>{place.description}</p>
            <div className="tag-row">{place.best_for.map((tag) => <span key={tag}>{tag}</span>)}</div>
            <dl><div><dt>Time</dt><dd>{place.recommended_days} days</dd></div><div><dt>Relevance</dt><dd>{place.relevance_score}/10</dd></div></dl>
          </label>
        })}</div>
        <div className="selection-bar"><span>{saved ? 'Route saved. Ready for an itinerary.' : `${selectedCount} places in this route`}</span><Button onClick={() => save.mutate(selection.size ? [...selection] : available.filter((place) => place.selected).map((place) => place.id))} disabled={!selectedCount || save.isPending}>{save.isPending ? 'Saving…' : 'Save selected places'}</Button></div>
      </section> : <div className="plan-prompt"><Sparkles /><h2>See what fits</h2><p>Run analysis to compare weather, time, cost, and travel efficiency.</p></div>}
    </>
  )
}
