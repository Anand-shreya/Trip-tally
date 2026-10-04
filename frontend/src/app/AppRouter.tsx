import { Route, Routes } from 'react-router-dom'
import { Link } from 'react-router-dom'

import { RootShell, TripLayout } from './AppShell'
import { DashboardPage } from '../pages/DashboardPage'
import { ExpensesPage } from '../pages/ExpensesPage'
import { ItineraryPage } from '../pages/ItineraryPage'
import { NewTripPage } from '../pages/NewTripPage'
import { OverviewPage } from '../pages/OverviewPage'
import { PeoplePage } from '../pages/PeoplePage'
import { PlanPage } from '../pages/PlanPage'
import { SummaryPage } from '../pages/SummaryPage'

function NotFound() { return <main className="standalone"><h1>That route isn’t on the map.</h1><Link to="/">Return to trips</Link></main> }

export function AppRouter() {
  return (
    <Routes>
      <Route element={<RootShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="trips/new" element={<NewTripPage />} />
        <Route path="trips/:id" element={<TripLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="plan" element={<PlanPage />} />
          <Route path="itinerary" element={<ItineraryPage />} />
          <Route path="expenses" element={<ExpensesPage />} />
          <Route path="people" element={<PeoplePage />} />
          <Route path="summary" element={<SummaryPage />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
