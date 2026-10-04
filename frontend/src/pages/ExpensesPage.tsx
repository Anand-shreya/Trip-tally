import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BedDouble, CarFront, Plus, ReceiptText, Soup, Ticket, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button, EmptyState, ErrorState, LoadingState, Modal, PageHeader } from '../components/ui'
import { ExpenseForm } from '../features/expenses/ExpenseForm'
import { api } from '../lib/api'
import { formatDate, formatMoney } from '../lib/format'
import { useExpenses, useTravelers, useTrip } from '../lib/queries'
import { queryKeys } from '../lib/queryKeys'
import type { ExpenseCategory } from '../lib/types'

const filters: Array<'' | ExpenseCategory> = ['', 'FOOD', 'ACCOMMODATION', 'TRANSPORT', 'ACTIVITIES', 'OTHER']
const categoryIcon = (category: ExpenseCategory) => category === 'FOOD' ? <Soup /> : category === 'ACCOMMODATION' ? <BedDouble /> : category === 'TRANSPORT' ? <CarFront /> : category === 'TICKETS' ? <Ticket /> : <ReceiptText />

export function ExpensesPage() {
  const { id = '' } = useParams()
  const client = useQueryClient()
  const [category, setCategory] = useState<'' | ExpenseCategory>('')
  const [showForm, setShowForm] = useState(false)
  const trip = useTrip(id)
  const travelers = useTravelers(id)
  const expenses = useExpenses(id, category)
  const remove = useMutation({ mutationFn: (expenseId: string) => api.delete(`/trips/${id}/expenses/${expenseId}`), onSuccess: () => refresh() })
  function refresh() {
    client.invalidateQueries({ queryKey: ['trips', id, 'expenses'] })
    client.invalidateQueries({ queryKey: queryKeys.balances(id) })
    client.invalidateQueries({ queryKey: queryKeys.summary(id) })
  }
  const totals = useMemo(() => (expenses.data ?? []).reduce<Record<string, number>>((result, expense) => ({ ...result, [expense.category]: (result[expense.category] ?? 0) + Number(expense.base_amount) }), {}), [expenses.data])
  const total = Object.values(totals).reduce((sum, value) => sum + value, 0)
  if (trip.isLoading || travelers.isLoading || expenses.isLoading) return <LoadingState label="Balancing the ledger…" />
  if (trip.isError || travelers.isError || expenses.isError || !trip.data) return <ErrorState error={trip.error ?? travelers.error ?? expenses.error} />
  const names = Object.fromEntries((travelers.data ?? []).map((traveler) => [traveler.id, traveler.name]))
  return (
    <>
      <PageHeader title="Shared ledger" intro="Record what happened. The exact splits and final transfers follow automatically." action={<Button onClick={() => setShowForm(true)}><Plus size={18} /> Add expense</Button>} />
      <section className="expense-total"><span>Total spent</span><strong>{formatMoney(total, trip.data.base_currency)}</strong><p>{expenses.data?.length ?? 0} recorded expenses</p></section>
      <div className="category-strip">{Object.entries(totals).map(([name, value]) => <div key={name}><span>{name.toLowerCase()}</span><strong>{formatMoney(value, trip.data!.base_currency)}</strong></div>)}</div>
      <div className="filter-row" aria-label="Expense filters">{filters.map((item) => <button className={category === item ? 'active' : ''} key={item || 'ALL'} onClick={() => setCategory(item)}>{item ? item.toLowerCase() : 'all'}</button>)}</div>
      {!expenses.data?.length ? <EmptyState title="No expenses here" message="Add the first expense or change the active category filter." action={<Button onClick={() => setShowForm(true)}>Add expense</Button>} /> : <div className="expense-list">{expenses.data.map((expense) => <article key={expense.id}><span className="expense-icon">{categoryIcon(expense.category)}</span><div><h3>{expense.description}</h3><p>{formatDate(expense.expense_date)} · Paid by {names[expense.paid_by] ?? 'Traveler'} · Split {expense.splits.length} ways</p></div><strong>{formatMoney(expense.base_amount, trip.data!.base_currency)}</strong><button className="icon-button" aria-label={`Delete ${expense.description}`} onClick={() => remove.mutate(expense.id)}><Trash2 size={17} /></button></article>)}</div>}
      {showForm && <Modal title="Add expense" onClose={() => setShowForm(false)}><ExpenseForm tripId={id} travelers={travelers.data ?? []} baseCurrency={trip.data.base_currency} onCreated={() => { setShowForm(false); refresh() }} /></Modal>}
    </>
  )
}
