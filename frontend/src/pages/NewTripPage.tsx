import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CalendarDays, MapPin, Users } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '../components/ui'
import { api } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'

const schema = z.object({
  name: z.string().trim().min(1),
  destination: z.string().trim().min(1),
  start_date: z.string().min(1),
  number_of_days: z.coerce.number().int().min(1).max(60),
  budget: z.string(),
  currency: z.string().length(3),
  travel_style: z.enum(['BUDGET', 'COMFORTABLE', 'PREMIUM']),
  travelers: z.string().min(1),
})
type FormValues = z.infer<typeof schema>

export function NewTripPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState('')
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    defaultValues: { number_of_days: 5, currency: 'INR', travel_style: 'COMFORTABLE', budget: '', travelers: '' },
  })
  const create = useMutation({
    mutationFn: async (values: FormValues) => {
      const parsed = schema.parse(values)
      const names = parsed.travelers.split(/[,\n]/).map((name) => name.trim()).filter(Boolean)
      const trip = await api.post<{ trip_id: string; status: string }>('/trips', {
        name: parsed.name,
        destination: parsed.destination,
        start_date: parsed.start_date,
        number_of_days: parsed.number_of_days,
        budget: parsed.budget ? Number(parsed.budget) : null,
        currency: parsed.currency.toUpperCase(),
        travel_style: parsed.travel_style,
      })
      await Promise.all(names.map((name) => api.post(`/trips/${trip.trip_id}/travelers`, { name })))
      return trip
    },
    onSuccess: async (trip) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.trips })
      navigate(`/trips/${trip.trip_id}/plan`)
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : 'Could not create the trip.'),
  })
  const submit = handleSubmit((values) => {
    setFormError('')
    const parsed = schema.safeParse(values)
    if (!parsed.success) { setFormError('Complete the required trip details.'); return }
    create.mutate(parsed.data)
  })
  return (
    <main className="new-trip-page">
      <section className="new-trip-intro">
        <Link to="/"><ArrowLeft size={18} /> Back to trips</Link>
        <div><MapPin /><p>Start with the known details. The route can evolve.</p></div>
        <h1>Plot a new journey.</h1>
      </section>
      <section className="new-trip-form-wrap">
        <form className="trip-form" onSubmit={submit} noValidate>
          <div className="form-section"><span className="form-marker"><MapPin /></span><div><h2>Where</h2><p>Name the route and its main destination.</p></div></div>
          <label>Trip name<input {...register('name', { required: true })} placeholder="Sri Lanka loop" />{errors.name && <small>Trip name is required.</small>}</label>
          <label>Destination<input {...register('destination', { required: true })} placeholder="Sri Lanka" />{errors.destination && <small>Destination is required.</small>}</label>
          <div className="form-section"><span className="form-marker"><CalendarDays /></span><div><h2>When & how</h2><p>Set the dates, comfort, and guardrails.</p></div></div>
          <div className="form-row"><label>Start date<input type="date" {...register('start_date', { required: true })} /></label><label>Days<input type="number" min="1" max="60" {...register('number_of_days', { valueAsNumber: true })} /></label></div>
          <div className="form-row"><label>Budget<input type="number" min="0" step="0.01" {...register('budget')} placeholder="80000" /></label><label>Currency<input maxLength={3} {...register('currency')} /></label></div>
          <label>Travel style<select {...register('travel_style')}><option value="BUDGET">Budget</option><option value="COMFORTABLE">Comfortable</option><option value="PREMIUM">Premium</option></select></label>
          <div className="form-section"><span className="form-marker"><Users /></span><div><h2>Who</h2><p>Separate names with commas or new lines.</p></div></div>
          <label>Traveler names<textarea rows={3} {...register('travelers', { required: true })} placeholder="Shreya, Rahul, Ananya" /></label>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <Button type="submit" disabled={create.isPending}>{create.isPending ? 'Creating route…' : 'Create trip'}</Button>
        </form>
      </section>
    </main>
  )
}
