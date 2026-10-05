import { CalendarDays, MapPin, Plane, Users, WalletCards } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { TripActions } from '../components/TripActions'
import { ErrorState, LoadingState, PageHeader, Stat } from '../components/ui'
import { formatDate, formatMoney } from '../lib/format'
import { usePlaces, useTrip } from '../lib/queries'

export function OverviewPage() {
  const { id = '' } = useParams()
  const trip = useTrip(id)
  const places = usePlaces(id)
  if (trip.isLoading) return <LoadingState />
  if (trip.isError || !trip.data) return <ErrorState error={trip.error} retry={() => trip.refetch()} />
  const data = trip.data
  return (
    <>
      <PageHeader title={data.destination} intro={`${formatDate(data.start_date)} – ${formatDate(data.end_date)}`} action={<div className="trip-header-actions"><TripActions trip={data} /><Link className="button" to="plan">Continue planning</Link></div>} />
      <section className="overview-grid">
        <article className="overview-lead"><span className="map-coordinate"><MapPin /> {data.destination}</span><h2>{data.name}</h2><p>{data.number_of_days} days shaped around a {data.travel_style.toLowerCase()} pace.</p><div className="route-sketch"><span /><span /><span /></div></article>
        <article className="overview-stats"><Stat label="Current weather" value={data.weather_summary ?? 'Not analyzed'} note={data.weather_summary ? 'Latest saved provider observation.' : 'Run analysis to fetch current conditions.'} /><Stat label="Trip budget" value={data.budget ? formatMoney(data.budget, data.base_currency) : 'Open'} /><Stat label="Typical estimate" value={data.estimated_cost ? formatMoney(data.estimated_cost, data.base_currency) : 'Not estimated'} note={data.estimated_cost ? 'Latest saved Gemini estimate.' : undefined} /></article>
      </section>
      <section className="overview-strip">
        <div><CalendarDays /><span>Duration</span><strong>{data.number_of_days} days</strong></div>
        <div><Users /><span>Travelers</span><strong>{data.travelers.length}</strong></div>
        <div><Plane /><span>Departure</span><strong>{data.departure_city ?? 'Add in plan'}</strong></div>
        <div><WalletCards /><span>Selected stops</span><strong>{places.data?.filter((place) => place.selected).length ?? 0}</strong></div>
      </section>
    </>
  )
}
