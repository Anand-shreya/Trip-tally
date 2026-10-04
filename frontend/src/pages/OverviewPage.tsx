import { CalendarDays, CloudSun, MapPin, Users, WalletCards } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

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
      <PageHeader title={data.destination} intro={`${formatDate(data.start_date)} – ${formatDate(data.end_date)}`} action={<Link className="button" to="plan">Continue planning</Link>} />
      <section className="overview-grid">
        <article className="overview-lead"><span className="map-coordinate"><MapPin /> {data.destination}</span><h2>{data.name}</h2><p>{data.number_of_days} days shaped around a {data.travel_style.toLowerCase()} pace.</p><div className="route-sketch"><span /><span /><span /></div></article>
        <article className="overview-stats"><Stat label="Weather fit" value={data.weather_score ? `${data.weather_score}/10` : 'Not checked'} note={data.weather_summary ?? 'Run analysis to check the season.'} /><Stat label="Trip budget" value={data.budget ? formatMoney(data.budget, data.base_currency) : 'Open'} /><Stat label="Typical estimate" value={data.estimated_cost ? formatMoney(data.estimated_cost, data.base_currency) : 'Not estimated'} /></article>
      </section>
      <section className="overview-strip">
        <div><CalendarDays /><span>Duration</span><strong>{data.number_of_days} days</strong></div>
        <div><Users /><span>Travelers</span><strong>{data.travelers.length}</strong></div>
        <div><CloudSun /><span>Weather</span><strong>{data.weather_rating?.toLowerCase() ?? 'Pending'}</strong></div>
        <div><WalletCards /><span>Selected stops</span><strong>{places.data?.filter((place) => place.selected).length ?? 0}</strong></div>
      </section>
    </>
  )
}
