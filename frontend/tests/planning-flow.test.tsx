import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { usePlanningAnalysis } from '../src/lib/queries'
import { queryKeys } from '../src/lib/queryKeys'
import type { PlanningAnalysis, Trip } from '../src/lib/types'
import { NewTripPage } from '../src/pages/NewTripPage'
import { OverviewPage } from '../src/pages/OverviewPage'
import { PlanPage } from '../src/pages/PlanPage'

function renderPage(node: ReactNode, path = '/', pattern = '*') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path={pattern} element={node} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const trip: Trip = {
  id: 'trip-1',
  name: 'Delhi weekend',
  departure_city: 'Bengaluru',
  destination: 'Delhi',
  start_date: '2027-04-04',
  end_date: '2027-04-08',
  number_of_days: 5,
  base_currency: 'INR',
  budget: '150000.00',
  travel_style: 'COMFORTABLE',
  status: 'READY',
  is_archived: false,
  archived_at: null,
  weather_score: null,
  weather_rating: null,
  weather_summary: 'Current conditions in Delhi: clear sky, 24°C.',
  estimated_cost_min: '91000',
  estimated_cost: '125000',
  estimated_cost_max: '161000',
  travelers: [],
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-05T12:00:00Z',
}

const redFort = {
  id: 'red-fort',
  name: 'Red Fort',
  description: 'A Mughal citadel at the heart of Old Delhi.',
  latitude: 28.6562,
  longitude: 77.241,
  recommended_days: '0.5',
  relevance_score: '9.7',
  best_for: ['History', 'Architecture'],
  selected: true,
}

const indiaGate = {
  id: 'india-gate',
  name: 'India Gate',
  description: 'A landmark and gathering place on the ceremonial axis.',
  latitude: 28.6129,
  longitude: 77.2295,
  recommended_days: '0.5',
  relevance_score: '8.8',
  best_for: ['Landmark', 'Evening'],
  selected: false,
}

const analysis: PlanningAnalysis = {
  weather: {
    location: {
      name: 'Delhi',
      country_code: 'IN',
      latitude: 28.6139,
      longitude: 77.209,
      timezone_offset_seconds: 19800,
    },
    current: {
      observed_at: '2026-10-05T12:00:00Z',
      condition: 'Clear',
      description: 'clear sky',
      temperature_c: '24.0',
      feels_like_c: '25.0',
      minimum_c: '18.0',
      maximum_c: '27.0',
      humidity_percent: 55,
      pressure_hpa: 1014,
      visibility_m: 10000,
      cloud_percent: 5,
      wind_speed_kph: '8.0',
      wind_direction_degrees: 120,
      rain_mm_1h: null,
      snow_mm_1h: null,
      sunrise_at: '2026-10-05T00:45:00Z',
      sunset_at: '2026-10-05T12:32:00Z',
    },
    daily: [
      {
        requested_date: '2027-04-04',
        source_date: '2027-04-04',
        source: 'forecast',
        minimum_c: '16.0',
        maximum_c: '29.0',
        representative_c: '24.0',
        condition: 'Clear',
        precipitation_probability_percent: 10,
        precipitation_mm: null,
        humidity_percent: 48,
        maximum_wind_kph: '13.0',
      },
      {
        requested_date: '2027-04-05',
        source_date: '2026-04-05',
        source: 'historical',
        minimum_c: '17.0',
        maximum_c: '31.0',
        representative_c: '25.0',
        condition: 'Partly cloudy',
        precipitation_probability_percent: null,
        precipitation_mm: '0.4',
        humidity_percent: null,
        maximum_wind_kph: '11.0',
      },
    ],
    source: 'openweather+open-meteo',
    summary: 'Current conditions in Delhi: clear sky, 24°C.',
  },
  budget: {
    currency: 'INR',
    traveler_count: 1,
    number_of_days: 5,
    categories: {
      flights: { minimum: '50000', typical: '60000', maximum: '70000' },
      accommodation: { minimum: '20000', typical: '30000', maximum: '40000' },
      food: { minimum: '8000', typical: '12000', maximum: '16000' },
      local_transport: { minimum: '5000', typical: '8000', maximum: '12000' },
      tickets: { minimum: '3000', typical: '5000', maximum: '8000' },
      activities: { minimum: '5000', typical: '10000', maximum: '15000' },
    },
    total: { minimum: '91000', typical: '125000', maximum: '161000' },
  },
  places: [redFort, indiaGate],
  weather_source: 'openweather+open-meteo',
  budget_model: 'gemini-3.5-flash-lite',
  analyzed_at: '2026-10-05T12:05:00Z',
  status: 'READY',
}

function planningFetch(options?: {
  tripResponse?: typeof trip
  analysisResponse?: typeof analysis | null
  analyzeResponse?: typeof analysis | Response | Promise<Response>
}) {
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === 'POST' && url.endsWith('/analyze')) {
      if (options?.analyzeResponse instanceof Response) return options.analyzeResponse
      if (options?.analyzeResponse instanceof Promise) return options.analyzeResponse
      return new Response(JSON.stringify(options?.analyzeResponse ?? analysis))
    }
    if (init?.method === 'POST' && url.endsWith('/places/select')) {
      return new Response(JSON.stringify([redFort, { ...indiaGate, selected: true }]))
    }
    if (!init?.method && url.endsWith('/trips/trip-1')) {
      return new Response(JSON.stringify(options?.tripResponse ?? trip))
    }
    if (!init?.method && url.endsWith('/trips/trip-1/analysis')) {
      if (options?.analysisResponse === null) {
        return new Response(JSON.stringify({ detail: 'Analysis not found' }), { status: 404 })
      }
      return new Response(JSON.stringify(options?.analysisResponse ?? analysis))
    }
    return new Response('{}', { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPlan() {
  return renderPage(<PlanPage />, '/trips/trip-1/plan', '/trips/:id/plan')
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('trip creation', () => {
  it('selects locations with the keyboard, submits coordinates, then adds every traveler', async () => {
    const calls: Array<{ url: string; body: Record<string, unknown> }> = []
    vi.stubGlobal('fetch', vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      const body = init?.body ? JSON.parse(String(init.body)) : null
      if (url.includes('/locations/search')) {
        const isDeparture = url.includes('kind=departure')
        return new Response(JSON.stringify([isDeparture ? {
          id: 'R:1',
          label: 'New Delhi, Delhi, India',
          name: 'New Delhi',
          country_code: 'IN',
          latitude: 28.6139,
          longitude: 77.209,
          location_type: 'city',
        } : {
          id: 'R:2',
          label: 'Sri Lanka',
          name: 'Sri Lanka',
          country_code: 'LK',
          latitude: 7.8774,
          longitude: 80.7011,
          location_type: 'country',
        }]))
      }
      calls.push({ url, body })
      if (url.endsWith('/trips')) {
        return new Response(JSON.stringify({ trip_id: 'trip-1', status: 'PLANNING' }), { status: 201 })
      }
      return new Response(JSON.stringify({
        id: `person-${calls.length}`,
        name: body.name,
        email: null,
        created_at: '2026-01-01T00:00:00Z',
      }), { status: 201 })
    }))
    renderPage(<NewTripPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText(/trip name/i), 'Island loop')
    await user.type(screen.getByLabelText(/departure city/i), 'Del')
    expect(await screen.findByRole('option', { name: /New Delhi, Delhi, India.*IN/i })).toBeInTheDocument()
    await user.keyboard('{ArrowDown}{Enter}')
    expect(screen.getByLabelText(/departure city/i)).toHaveValue('New Delhi, Delhi, India')
    await user.type(screen.getByLabelText(/destination/i), 'Sri')
    expect(await screen.findByRole('option', { name: /Sri Lanka.*LK/i })).toBeInTheDocument()
    await user.keyboard('{ArrowDown}{Enter}')
    await user.type(screen.getByLabelText(/start date/i), '2026-09-05')
    await user.clear(screen.getByLabelText(/days/i))
    await user.type(screen.getByLabelText(/days/i), '3')
    await user.type(screen.getByLabelText(/traveler names/i), 'Shreya, Rahul, Amit')
    await user.click(screen.getByRole('button', { name: /create trip/i }))

    await waitFor(() => expect(calls).toHaveLength(4))
    expect(calls[0].body).toMatchObject({
      departure_city: 'New Delhi, Delhi, India',
      destination: 'Sri Lanka',
      departure_location: {
        label: 'New Delhi, Delhi, India',
        country_code: 'IN',
        latitude: 28.6139,
        longitude: 77.209,
        location_type: 'city',
      },
      destination_location: {
        label: 'Sri Lanka',
        country_code: 'LK',
        latitude: 7.8774,
        longitude: 80.7011,
        location_type: 'country',
      },
    })
    expect(calls.slice(1).map((call) => call.body.name)).toEqual(['Shreya', 'Rahul', 'Amit'])
  })

  it('waits for two characters and debounces location searches', async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      void input
      void init
      return new Response(JSON.stringify([]))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage(<NewTripPage />)
    const user = userEvent.setup()
    const departure = screen.getByLabelText(/departure city/i)

    await user.type(departure, 'D')
    await new Promise((resolve) => setTimeout(resolve, 350))
    expect(fetchMock).not.toHaveBeenCalled()

    await user.type(departure, 'e')
    expect(fetchMock).not.toHaveBeenCalled()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(String(fetchMock.mock.calls[0][0])).toContain('/locations/search?q=De&kind=departure')
  })

  it('ignores option navigation while a location search has no results yet', async () => {
    let finishSearch: ((response: Response) => void) | undefined
    const fetchMock = vi.fn(async () => new Promise<Response>((resolve) => {
      finishSearch = resolve
    }))
    vi.stubGlobal('fetch', fetchMock)
    renderPage(<NewTripPage />)
    const user = userEvent.setup()
    const departure = screen.getByLabelText(/departure city/i)

    await user.type(departure, 'De')
    expect(await screen.findByLabelText('Searching')).toBeInTheDocument()
    await user.keyboard('{ArrowUp}{Enter}')

    expect(departure).toHaveValue('De')
    finishSearch?.(new Response(JSON.stringify([])))
    await waitFor(() => expect(screen.queryByLabelText('Searching')).not.toBeInTheDocument())
  })

  it('rejects ambiguous free text when no suggested location was selected', async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      void input
      void init
      return new Response(JSON.stringify([]))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage(<NewTripPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText(/trip name/i), 'Island loop')
    await user.type(screen.getByLabelText(/departure city/i), 'Delhi')
    await user.type(screen.getByLabelText(/destination/i), 'Sri Lanka')
    await user.type(screen.getByLabelText(/start date/i), '2026-09-05')
    await user.type(screen.getByLabelText(/traveler names/i), 'Shreya')
    await user.click(screen.getByRole('button', { name: /create trip/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Select a departure city and destination from the suggestions.',
    )
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })
})

describe('planning analysis reads', () => {
  it('loads an absent saved analysis once without posting or showing an error', async () => {
    const fetchMock = vi.fn(async () => (
      new Response(JSON.stringify({ detail: 'Analysis not found' }), { status: 404 })
    ))
    vi.stubGlobal('fetch', fetchMock)

    function AnalysisProbe() {
      const saved = usePlanningAnalysis('trip-1')
      if (saved.isLoading) return <p>Loading analysis</p>
      if (saved.isError) return <p>Analysis failed</p>
      return <p>{saved.data === null ? 'No analysis yet' : 'Analysis ready'}</p>
    }

    renderPage(<AnalysisProbe />)

    expect(await screen.findByText('No analysis yet')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/trips/trip-1/analysis'),
      expect.not.objectContaining({ method: 'POST' }),
    )
  })

  it('renders the complete persisted weather, budget, and place report using GETs only', async () => {
    const fetchMock = planningFetch()
    renderPlan()

    expect(await screen.findByRole('heading', { name: 'Delhi, IN' })).toBeInTheDocument()
    expect(screen.getByText('Observed 5 Oct 2026, 12:00 UTC')).toBeInTheDocument()
    expect(screen.getByText('Analysis updated 5 Oct 2026, 12:05 UTC')).toBeInTheDocument()
    expect(screen.getByText('OpenWeather + Open-Meteo')).toBeInTheDocument()
    expect(screen.getByText('Feels like 25°C')).toBeInTheDocument()
    expect(screen.getByText('27°C / 18°C')).toBeInTheDocument()
    expect(screen.getByText('55%')).toBeInTheDocument()
    expect(screen.getByText('1,014 hPa')).toBeInTheDocument()
    expect(screen.getByText('10 km')).toBeInTheDocument()
    expect(screen.getByText('5%')).toBeInTheDocument()
    expect(screen.getByText('8 km/h · 120°')).toBeInTheDocument()
    expect(screen.getByText('00:45 UTC')).toBeInTheDocument()
    expect(screen.getByText('12:32 UTC')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Forecast for your dates' })).toBeInTheDocument()
    expect(screen.getByText('4 Apr 2027')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Typical weather from recent history' })).toBeInTheDocument()
    expect(screen.getByText('Based on 5 Apr 2026')).toBeInTheDocument()

    const budget = screen.getByRole('region', { name: 'Trip budget estimate' })
    expect(within(budget).getByText('₹1,25,000')).toBeInTheDocument()
    expect(within(budget).getByText('₹91,000 – ₹1,61,000')).toBeInTheDocument()
    expect(within(budget).getByText('1 traveler · 5 days')).toBeInTheDocument()
    for (const label of [
      'Round-trip economy flights · 1 traveler',
      'Accommodation',
      'Food',
      'Local transport',
      'Tickets',
      'Activities',
    ]) {
      expect(within(budget).getByRole('row', { name: new RegExp(label, 'i') })).toBeInTheDocument()
    }
    expect(within(budget).getByText('gemini-3.5-flash-lite')).toBeInTheDocument()
    expect(within(budget).getByText('Gemini estimate—not a live quote')).toBeInTheDocument()

    const place = screen.getByRole('article', { name: 'Red Fort' })
    expect(within(place).getByText(redFort.description)).toBeInTheDocument()
    expect(within(place).getByText('0.5 days')).toBeInTheDocument()
    expect(within(place).getByText('History')).toBeInTheDocument()
    expect(within(place).getByText('9.7/10 relevance')).toBeInTheDocument()
    const mapLink = within(place).getByRole('link', { name: /open red fort in google maps/i })
    expect(mapLink).toHaveAttribute(
      'href',
      'https://www.google.com/maps/search/?api=1&query=Red%20Fort%20Delhi',
    )
    expect(mapLink).toHaveAttribute('target', '_blank')
    expect(mapLink).toHaveAttribute('rel', expect.stringContaining('noopener'))
    expect(screen.queryByText(/per-place estimate/i)).not.toBeInTheDocument()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method)).toBe(true)
  })

  it('shows current rain and snow volumes when the provider returns them', async () => {
    planningFetch({
      analysisResponse: {
        ...analysis,
        weather: {
          ...analysis.weather,
          current: {
            ...analysis.weather.current,
            rain_mm_1h: '0.4',
            snow_mm_1h: '0.2',
          },
        },
      },
    })
    renderPlan()

    const weather = await screen.findByRole('region', { name: 'Weather report' })
    const currentDetails = weather.querySelector('.weather-details')
    expect(currentDetails).not.toBeNull()
    expect(within(weather).getByText('Rain (1h)')).toBeInTheDocument()
    expect(within(currentDetails as HTMLElement).getByText('0.4 mm')).toBeInTheDocument()
    expect(within(weather).getByText('Snow (1h)')).toBeInTheDocument()
    expect(within(currentDetails as HTMLElement).getByText('0.2 mm')).toBeInTheDocument()
  })

  it('labels flights as round-trip economy for the full traveler count', async () => {
    planningFetch()
    renderPlan()

    const budget = await screen.findByRole('region', { name: 'Trip budget estimate' })
    expect(within(budget).getByRole('rowheader', {
      name: 'Round-trip economy flights · 1 traveler',
    })).toBeInTheDocument()
  })
})

describe('planning analysis interactions', () => {
  it('requires a departure city for a legacy trip and sends it with analysis', async () => {
    const fetchMock = planningFetch({
      tripResponse: { ...trip, departure_city: null, status: 'PLANNING' },
      analysisResponse: null,
    })
    renderPlan()
    const user = userEvent.setup()

    const departure = await screen.findByLabelText(/departure city/i)
    await user.click(screen.getByRole('button', { name: 'Analyze trip' }))
    expect(screen.getByText('Departure city is required.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)

    await user.type(departure, 'Mumbai')
    await user.click(screen.getByRole('button', { name: 'Analyze trip' }))

    await screen.findByRole('heading', { name: 'Delhi, IN' })
    const analyzeCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/analyze'))
    expect(JSON.parse(String(analyzeCall?.[1]?.body))).toEqual({ departure_city: 'Mumbai' })
  })

  it('posts an empty object for a stored origin and explains all loading work', async () => {
    let resolveAnalysis!: (response: Response) => void
    const pending = new Promise<Response>((resolve) => { resolveAnalysis = resolve })
    const fetchMock = planningFetch({ analysisResponse: null, analyzeResponse: pending })
    renderPlan()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Analyze trip' }))
    expect(screen.getByRole('status')).toHaveTextContent(
      'Fetching weather, budget, and places…',
    )
    const analyzeCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/analyze'))
    expect(JSON.parse(String(analyzeCall?.[1]?.body))).toEqual({})

    resolveAnalysis(new Response(JSON.stringify(analysis)))
    expect(await screen.findByRole('heading', { name: 'Delhi, IN' })).toBeInTheDocument()
  })

  it('keeps the saved report visible when a provider refresh fails', async () => {
    planningFetch({
      analyzeResponse: new Response(
        JSON.stringify({ detail: { code: 'budget_unavailable' } }),
        { status: 502 },
      ),
    })
    renderPlan()
    const user = userEvent.setup()

    expect(await screen.findByRole('heading', { name: 'Delhi, IN' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Refresh analysis' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Gemini could not estimate the budget. Your saved analysis is still here.',
    )
    expect(screen.getByRole('heading', { name: 'Delhi, IN' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Red Fort' })).toBeInTheDocument()
  })

  it('preserves refreshed selections and saves them with a separate request', async () => {
    const fetchMock = planningFetch()
    renderPlan()
    const user = userEvent.setup()

    await screen.findByRole('heading', { name: 'Delhi, IN' })
    await user.click(screen.getByRole('button', { name: 'Refresh analysis' }))
    const redFortCheckbox = await screen.findByRole('checkbox', { name: 'Select Red Fort' })
    expect(redFortCheckbox).toBeChecked()
    const indiaGateCheckbox = screen.getByRole('checkbox', { name: 'Select India Gate' })
    expect(indiaGateCheckbox).not.toBeChecked()

    await user.click(indiaGateCheckbox)
    await user.click(screen.getByRole('button', { name: 'Save selected places' }))

    expect(await screen.findByText('Route saved. Ready for an itinerary.')).toBeInTheDocument()
    const selectCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/places/select'))
    expect(JSON.parse(String(selectCall?.[1]?.body))).toEqual({
      place_ids: ['red-fort', 'india-gate'],
    })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/analyze'))).toHaveLength(1)
  })
})

describe('overview planning compatibility', () => {
  it('shows API-sourced current weather without a fabricated fit score', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    })
    client.setQueryData(queryKeys.trip('trip-1'), {
      ...trip,
      weather_score: '8.7',
      weather_rating: 'EXCELLENT',
      weather_summary: 'Clear skies, 28°C with a light breeze.',
    })
    client.setQueryData(queryKeys.places('trip-1'), [])

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/trips/trip-1']}>
          <Routes><Route path="/trips/:id" element={<OverviewPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText(/current weather/i)).toBeInTheDocument()
    expect(screen.getByText(/clear.*28/i)).toBeInTheDocument()
    expect(screen.queryByText(/weather fit/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\/10/)).not.toBeInTheDocument()
  })
})
