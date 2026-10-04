import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, UserRoundPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'

import { Button, ErrorState, LoadingState, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { formatMoney, initials } from '../lib/format'
import { useBalances, useTravelers, useTrip } from '../lib/queries'
import { queryKeys } from '../lib/queryKeys'

export function PeoplePage() {
  const { id = '' } = useParams()
  const client = useQueryClient()
  const [name, setName] = useState('')
  const trip = useTrip(id)
  const travelers = useTravelers(id)
  const balances = useBalances(id)
  const add = useMutation({
    mutationFn: (travelerName: string) => api.post(`/trips/${id}/travelers`, { name: travelerName }),
    onSuccess: () => { setName(''); client.invalidateQueries({ queryKey: queryKeys.travelers(id) }); client.invalidateQueries({ queryKey: queryKeys.trip(id) }) },
  })
  const submit = (event: FormEvent) => { event.preventDefault(); if (name.trim()) add.mutate(name.trim()) }
  if (trip.isLoading || travelers.isLoading || balances.isLoading) return <LoadingState label="Gathering the group…" />
  if (trip.isError || travelers.isError || balances.isError || !trip.data) return <ErrorState error={trip.error ?? travelers.error ?? balances.error} />
  const balanceById = Object.fromEntries((balances.data ?? []).map((balance) => [balance.traveler_id, balance]))
  return (
    <>
      <PageHeader title="The travel party" intro="Everyone’s contribution stays visible without turning the trip into accounting." />
      <form className="add-person" onSubmit={submit}><UserRoundPlus /><label><span>Add a traveler</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Traveler name" /></label><Button type="submit" disabled={add.isPending}><Plus size={17} /> Add</Button></form>
      {add.isError && <p className="form-error" role="alert">{add.error.message}</p>}
      <div className="people-grid">{(travelers.data ?? []).map((traveler) => {
        const balance = balanceById[traveler.id]
        const net = Number(balance?.net ?? 0)
        return <article key={traveler.id}><div className="avatar">{initials(traveler.name)}</div><h2>{traveler.name}</h2><div className="person-ledger"><span>Paid<strong>{formatMoney(balance?.paid, trip.data!.base_currency)}</strong></span><span>Share<strong>{formatMoney(balance?.owed, trip.data!.base_currency)}</strong></span><span>Balance<strong className={net >= 0 ? 'positive' : 'negative'}>{net > 0 ? '+' : ''}{formatMoney(net, trip.data!.base_currency)}</strong></span></div></article>
      })}</div>
    </>
  )
}
