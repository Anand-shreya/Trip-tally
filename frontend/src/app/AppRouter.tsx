import { Route, Routes } from 'react-router-dom'
import { Link } from 'react-router-dom'

import { RootShell, TripLayout } from './AppShell'

function DashboardStub() {
  return <main className="dashboard-hero"><p className="kicker">Your routes, costs, and shared memories</p><h1>Where to next?</h1><p>Build a thoughtful itinerary, keep the group budget visible, and finish with fair settlements.</p><Link className="button" to="/trips/new">Plan a trip</Link></main>
}

function NewTripStub() { return <main className="standalone"><h1>Plan a new trip</h1></main> }
function TripPageStub() { return <section><h1>Trip overview</h1></section> }
function RoutePageStub({ title }: { title: string }) { return <section><h1>{title}</h1></section> }
function NotFound() { return <main className="standalone"><h1>That route isn’t on the map.</h1><Link to="/">Return to trips</Link></main> }

export function AppRouter() {
  return (
    <Routes>
      <Route element={<RootShell />}>
        <Route index element={<DashboardStub />} />
        <Route path="trips/new" element={<NewTripStub />} />
        <Route path="trips/:id" element={<TripLayout />}>
          <Route index element={<TripPageStub />} />
          <Route path="plan" element={<RoutePageStub title="Plan" />} />
          <Route path="itinerary" element={<RoutePageStub title="Itinerary" />} />
          <Route path="expenses" element={<RoutePageStub title="Expenses" />} />
          <Route path="people" element={<RoutePageStub title="People" />} />
          <Route path="summary" element={<RoutePageStub title="Summary" />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
