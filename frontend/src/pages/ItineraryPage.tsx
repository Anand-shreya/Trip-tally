import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Clock3, MapPin, Sparkles } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { Button, EmptyState, ErrorState, LoadingState, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { formatDate, formatMoney } from '../lib/format'
import { useItinerary, useTrip } from '../lib/queries'
import { queryKeys } from '../lib/queryKeys'
import type { Job } from '../lib/types'

export function ItineraryPage() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const trip = useTrip(id)
  const itinerary = useItinerary(id)
  const generate = useMutation({
    mutationFn: () => api.post<Job>(`/trips/${id}/itinerary/generate`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.itinerary(id) }),
  })
  if (trip.isLoading || itinerary.isLoading) return <LoadingState label="Laying out each day…" />
  if (trip.isError || itinerary.isError || !trip.data) return <ErrorState error={trip.error ?? itinerary.error} retry={() => { trip.refetch(); itinerary.refetch() }} />
  return (
    <>
      <PageHeader title="Day by day" intro="A practical rhythm, with enough room for the trip to surprise you." action={<Button onClick={() => generate.mutate()} disabled={generate.isPending}>{generate.isPending ? 'Building itinerary…' : itinerary.data?.length ? 'Regenerate itinerary' : 'Generate itinerary'}</Button>} />
      {generate.isError && <ErrorState error={generate.error} />}
      {!itinerary.data?.length ? <EmptyState title="No itinerary yet" message="Select places in Plan, then generate a route for every day." action={<Button onClick={() => generate.mutate()}><Sparkles size={18} /> Generate itinerary</Button>} /> :
        <div className="itinerary-timeline">{itinerary.data.map((day) => <article className="itinerary-day" key={day.id}>
          <header><span>Day {day.day_number}</span><div><h2>{day.title}</h2><p>{formatDate(day.date)} · {day.summary}</p></div></header>
          <div className="activity-list">{day.activities.map((activity) => <div className="activity" key={activity.id}>
            <time><Clock3 />{activity.start_time.slice(0, 5)}</time><div><h3>{activity.title}</h3><p>{activity.description}</p><span><MapPin /> {activity.location_name}</span></div><strong>{formatMoney(activity.estimated_cost, trip.data.base_currency)}</strong>
          </div>)}</div>
        </article>)}</div>}
    </>
  )
}
