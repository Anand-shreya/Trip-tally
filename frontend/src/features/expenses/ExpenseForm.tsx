import { useState, type FormEvent } from 'react'

import { Button } from '../../components/ui'
import { api } from '../../lib/api'
import { formatMoney } from '../../lib/format'
import type { Expense, ExpenseCategory, Traveler } from '../../lib/types'

const categories: ExpenseCategory[] = ['FOOD', 'ACCOMMODATION', 'TRANSPORT', 'ACTIVITIES', 'TICKETS', 'SHOPPING', 'OTHER']

export function ExpenseForm({ tripId, travelers, baseCurrency, onCreated }: { tripId: string; travelers: Traveler[]; baseCurrency: string; onCreated: (expense: Expense) => void }) {
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState(baseCurrency)
  const [category, setCategory] = useState<ExpenseCategory>('FOOD')
  const [paidBy, setPaidBy] = useState(travelers[0]?.id ?? '')
  const [expenseDate, setExpenseDate] = useState(new Date().toISOString().slice(0, 10))
  const [included, setIncluded] = useState(() => new Set(travelers.map((traveler) => traveler.id)))
  const [splitType, setSplitType] = useState<'EQUAL' | 'CUSTOM'>('EQUAL')
  const [shares, setShares] = useState<Record<string, string>>({})
  const [location, setLocation] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const amountNumber = Number(amount || 0)
  const shareTotal = travelers.filter((traveler) => included.has(traveler.id)).reduce((sum, traveler) => sum + Number(shares[traveler.id] || 0), 0)
  const difference = amountNumber - shareTotal

  const toggleTraveler = (travelerId: string) => setIncluded((current) => {
    const next = new Set(current)
    if (next.has(travelerId)) next.delete(travelerId)
    else next.add(travelerId)
    return next
  })

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (!description.trim() || amountNumber <= 0 || !paidBy || !included.size) {
      setError('Description, positive amount, payer, and participants are required.')
      return
    }
    if (splitType === 'CUSTOM' && Math.abs(difference) > 0.005) {
      setError('Custom shares must equal the expense amount.')
      return
    }
    const participants = travelers.filter((traveler) => included.has(traveler.id))
    const payload = {
      description: description.trim(), amount: amountNumber, currency: currency.toUpperCase(), category,
      paid_by: paidBy, expense_date: expenseDate, included_travelers: participants.map((traveler) => traveler.id), split_type: splitType,
      splits: splitType === 'CUSTOM' ? participants.map((traveler) => ({ traveler_id: traveler.id, amount: Number(shares[traveler.id] || 0) })) : [],
      location: location.trim() || null, notes: notes.trim() || null,
    }
    setSaving(true)
    try {
      const key = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`
      const result = await api.post<Expense>(`/trips/${tripId}/expenses`, payload, { 'Idempotency-Key': key })
      onCreated(result)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not add the expense.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="expense-form" onSubmit={submit}>
      <label>Description<input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Dinner in Ella" /></label>
      <div className="form-row"><label>Amount<input type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><label>Currency<input value={currency} maxLength={3} onChange={(event) => setCurrency(event.target.value)} /></label></div>
      <div className="form-row"><label>Category<select value={category} onChange={(event) => setCategory(event.target.value as ExpenseCategory)}>{categories.map((item) => <option key={item} value={item}>{item.toLowerCase()}</option>)}</select></label><label>Paid by<select value={paidBy} onChange={(event) => setPaidBy(event.target.value)}>{travelers.map((traveler) => <option key={traveler.id} value={traveler.id}>{traveler.name}</option>)}</select></label></div>
      <label>Expense date<input type="date" value={expenseDate} onChange={(event) => setExpenseDate(event.target.value)} /></label>
      <fieldset><legend>Split between</legend><div className="participant-grid">{travelers.map((traveler) => <label key={traveler.id}><input type="checkbox" checked={included.has(traveler.id)} onChange={() => toggleTraveler(traveler.id)} /> {traveler.name}</label>)}</div></fieldset>
      <fieldset><legend>Split method</legend><div className="radio-row"><label><input type="radio" name="split" checked={splitType === 'EQUAL'} onChange={() => setSplitType('EQUAL')} /> Equal</label><label><input type="radio" name="split" checked={splitType === 'CUSTOM'} onChange={() => setSplitType('CUSTOM')} /> Custom</label></div></fieldset>
      {splitType === 'EQUAL' && included.size > 0 && amountNumber > 0 && <div className="split-preview"><span>Each person’s share</span><strong>{formatMoney(amountNumber / included.size, baseCurrency)}</strong></div>}
      {splitType === 'CUSTOM' && <div className="custom-splits">{travelers.filter((traveler) => included.has(traveler.id)).map((traveler) => <label key={traveler.id}>{traveler.name} share<input aria-label={`${traveler.name} share`} type="number" min="0" step="0.01" value={shares[traveler.id] ?? ''} onChange={(event) => setShares((current) => ({ ...current, [traveler.id]: event.target.value }))} /></label>)}<p className={Math.abs(difference) <= .005 ? 'balanced' : ''}>{Math.abs(difference) <= .005 ? 'Shares balanced' : `${formatMoney(Math.abs(difference), baseCurrency)} ${difference > 0 ? 'remaining' : 'over'}`}</p></div>}
      <div className="form-row"><label>Location <span>(optional)</span><input value={location} onChange={(event) => setLocation(event.target.value)} /></label><label>Notes <span>(optional)</span><input value={notes} onChange={(event) => setNotes(event.target.value)} /></label></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button type="submit" disabled={saving}>{saving ? 'Adding expense…' : 'Add expense'}</Button>
    </form>
  )
}
