import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ExpenseForm } from '../src/features/expenses/ExpenseForm'
import { SummaryPage } from '../src/pages/SummaryPage'
import type { Traveler } from '../src/lib/types'

const travelers: Traveler[] = [
  { id: 's', name: 'Shreya', email: null, created_at: '' },
  { id: 'r', name: 'Rahul', email: null, created_at: '' },
  { id: 'a', name: 'Amit', email: null, created_at: '' },
]

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function wrapper(node: ReactNode, path = '/', pattern = '*') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path={pattern} element={node} /></Routes></MemoryRouter></QueryClientProvider>)
}

describe('expense form', () => {
  it('submits selected participants as an equal split with an idempotency key', async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      void input
      void init
      return new Response(JSON.stringify({
        id: 'expense-1', trip_id: 'trip-1', description: 'Dinner', amount: '900', currency: 'INR', exchange_rate: '1',
        base_amount: '900', category: 'FOOD', paid_by: 's', expense_date: '2026-09-05', location: null, notes: null,
        created_at: '', splits: [],
      }), { status: 201 })
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    wrapper(<ExpenseForm tripId="trip-1" travelers={travelers} baseCurrency="INR" onCreated={() => undefined} />)

    await user.type(screen.getByLabelText(/description/i), 'Dinner')
    await user.type(screen.getByLabelText(/^amount/i), '900')
    await user.selectOptions(screen.getByLabelText(/paid by/i), 's')
    await user.click(screen.getByRole('checkbox', { name: /amit/i }))
    await user.click(screen.getByRole('button', { name: /add expense/i }))

    expect(fetchMock).toHaveBeenCalledOnce()
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(String(init?.body))
    expect(body.split_type).toBe('EQUAL')
    expect(body.included_travelers).toEqual(['s', 'r'])
    expect(new Headers(init?.headers).get('Idempotency-Key')).toBeTruthy()
  })

  it('shows custom share total feedback and blocks a mismatched total', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    wrapper(<ExpenseForm tripId="trip-1" travelers={travelers} baseCurrency="INR" onCreated={() => undefined} />)

    await user.type(screen.getByLabelText(/description/i), 'Rooms')
    await user.type(screen.getByLabelText(/^amount/i), '3000')
    await user.click(screen.getByRole('radio', { name: /custom/i }))
    await user.type(screen.getByLabelText(/shreya share/i), '1000')
    await user.type(screen.getByLabelText(/rahul share/i), '1000')
    await user.type(screen.getByLabelText(/amit share/i), '500')
    expect(screen.getByText(/₹500 remaining/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /add expense/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/must equal/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('summary', () => {
  it('renders budget, balances, and settlement instructions in trip currency', async () => {
    const summary = {
      trip_id: 'trip-1', trip_name: 'Island loop', destination: 'Sri Lanka', days: 3, currency: 'INR', budget: '30000',
      total_spent: '1200', remaining: '28800', average_per_day: '400', categories: { FOOD: '1200' },
      most_expensive_category: 'FOOD', most_expensive_expense: 'Dinner',
      traveler_balances: [
        { traveler_id: 's', traveler: 'Shreya', paid: '1200', owed: '600', net: '600' },
        { traveler_id: 'r', traveler: 'Rahul', paid: '0', owed: '600', net: '-600' },
      ],
      settlements: [{ from_traveler_id: 'r', from_traveler: 'Rahul', to_traveler_id: 's', to_traveler: 'Shreya', amount: '600' }],
      ai_summary: 'You stayed within budget and kept food spending visible.',
    }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(summary))))
    wrapper(<SummaryPage />, '/trips/trip-1/summary', '/trips/:id/summary')

    expect((await screen.findAllByText('₹1,200')).length).toBeGreaterThan(0)
    expect(screen.getByText(/rahul pays shreya/i)).toBeInTheDocument()
    expect(screen.getByText(/within budget/i)).toBeInTheDocument()
  })
})
