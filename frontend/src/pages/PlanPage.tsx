import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { BudgetReport } from '../components/planning/BudgetReport'
import { PlaceRecommendations } from '../components/planning/PlaceRecommendations'
import { WeatherReport } from '../components/planning/WeatherReport'
import { Button, ErrorState, LoadingState, PageHeader } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { usePlanningAnalysis, useTrip } from '../lib/queries'
import { queryKeys } from '../lib/queryKeys'
import type { Place, PlanningAnalysis } from '../lib/types'

const retryMessages: Record<string, string> = {
  weather_unavailable: 'Weather providers could not be reached. Your saved analysis is still here.',
  budget_unavailable: 'Gemini could not estimate the budget. Your saved analysis is still here.',
  places_unavailable: 'Gemini could not suggest places. Your saved analysis is still here.',
  invalid_provider_response: 'A provider returned invalid data. Your saved analysis is still here.',
}

function retryMessage(error: unknown): string {
  if (error instanceof ApiError && error.details && typeof error.details === 'object') {
    const code = 'code' in error.details ? error.details.code : undefined
    if (typeof code === 'string' && retryMessages[code]) return retryMessages[code]
  }
  return 'Analysis could not be refreshed. Your saved analysis is still here.'
}

export function PlanPage() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const trip = useTrip(id)
  const savedAnalysis = usePlanningAnalysis(id)
  const [departureCity, setDepartureCity] = useState('')
  const [departureError, setDepartureError] = useState('')
  const [selection, setSelection] = useState<Set<string> | null>(null)
  const [saved, setSaved] = useState(false)

  const analysis = useMutation({
    mutationFn: () => api.post<PlanningAnalysis>(
      `/trips/${id}/analyze`,
      trip.data?.departure_city ? {} : { departure_city: departureCity.trim() },
    ),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.analysis(id), result)
      queryClient.setQueryData(queryKeys.places(id), result.places)
      queryClient.invalidateQueries({ queryKey: queryKeys.trip(id), exact: true })
      setSelection(new Set(result.places.filter((place) => place.selected).map((place) => place.id)))
      setSaved(false)
    },
  })

  const report = savedAnalysis.data
  const activeSelection = selection ?? new Set(
    report?.places.filter((place) => place.selected).map((place) => place.id) ?? [],
  )
  const save = useMutation({
    mutationFn: () => api.post<Place[]>(`/trips/${id}/places/select`, {
      place_ids: [...activeSelection],
    }),
    onSuccess: (selectedPlaces) => {
      const selectedIds = new Set(selectedPlaces.map((place) => place.id))
      const mergeSelection = (places: Place[]) => places.map((place) => ({
        ...place,
        selected: selectedIds.has(place.id),
      }))
      queryClient.setQueryData<PlanningAnalysis | null>(
        queryKeys.analysis(id),
        (current) => current ? { ...current, places: mergeSelection(current.places) } : current,
      )
      queryClient.setQueryData<Place[]>(
        queryKeys.places(id),
        (current) => mergeSelection(current ?? report?.places ?? []),
      )
      setSelection(selectedIds)
      setSaved(true)
    },
  })

  if (trip.isLoading || savedAnalysis.isLoading) {
    return <LoadingState label="Loading the saved trip briefing…" />
  }
  if (trip.isError || !trip.data) {
    return <ErrorState error={trip.error} retry={() => trip.refetch()} />
  }
  if (savedAnalysis.isError) {
    return <ErrorState error={savedAnalysis.error} retry={() => savedAnalysis.refetch()} />
  }

  const tripData = trip.data
  const startAnalysis = () => {
    if (!tripData.departure_city && !departureCity.trim()) {
      setDepartureError('Departure city is required.')
      return
    }
    setDepartureError('')
    analysis.mutate()
  }
  const toggle = (placeId: string) => {
    setSaved(false)
    setSelection((current) => {
      const next = new Set(current ?? activeSelection)
      if (next.has(placeId)) next.delete(placeId)
      else next.add(placeId)
      return next
    })
  }

  const action = (
    <div className="planning-actions">
      {!tripData.departure_city && (
        <label className="departure-city-field">
          Departure city
          <input
            value={departureCity}
            onChange={(event) => {
              setDepartureCity(event.target.value)
              if (event.target.value.trim()) setDepartureError('')
            }}
            aria-invalid={!!departureError}
            placeholder="Mumbai"
          />
          {departureError && <small>{departureError}</small>}
        </label>
      )}
      <Button className="secondary" onClick={startAnalysis} disabled={analysis.isPending}>
        {analysis.isPending ? 'Analyzing…' : report ? 'Refresh analysis' : 'Analyze trip'}
      </Button>
    </div>
  )

  return (
    <>
      <PageHeader
        title="Shape the route"
        intro="Weather comes from weather services. Gemini estimates the group budget and suggests places."
        action={action}
      />
      {analysis.isPending && (
        <LoadingState label="Fetching weather, budget, and places…" />
      )}
      {analysis.isError && (
        <div className="planning-retry" role="alert">{retryMessage(analysis.error)}</div>
      )}

      {report ? (
        <div className="planning-report">
          <WeatherReport report={report.weather} analyzedAt={report.analyzed_at} />
          <BudgetReport report={report.budget} model={report.budget_model} />
          <PlaceRecommendations
            places={report.places}
            destination={tripData.destination}
            selection={activeSelection}
            onToggle={toggle}
            onSave={() => save.mutate()}
            isSaving={save.isPending}
            saved={saved}
          />
          {save.isError && <div className="planning-retry" role="alert">Selected places could not be saved. Try again.</div>}
        </div>
      ) : (
        <div className="plan-prompt">
          <Sparkles />
          <h2>Build your trip briefing</h2>
          <p>Analyze once to fetch weather, a flight-inclusive budget, and relevant places. Nothing runs until you choose Analyze trip.</p>
        </div>
      )}
    </>
  )
}
