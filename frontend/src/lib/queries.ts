import { useQuery } from '@tanstack/react-query'

import { api } from './api'
import { queryKeys } from './queryKeys'
import type { Balance, Expense, ItineraryDay, Place, Trip, TripSummary, Traveler } from './types'

export function useTrips() {
  return useQuery({ queryKey: queryKeys.trips, queryFn: () => api.get<Trip[]>('/trips') })
}

export function useTrip(tripId: string) {
  return useQuery({ queryKey: queryKeys.trip(tripId), queryFn: () => api.get<Trip>(`/trips/${tripId}`), enabled: !!tripId })
}

export function useTravelers(tripId: string) {
  return useQuery({ queryKey: queryKeys.travelers(tripId), queryFn: () => api.get<Traveler[]>(`/trips/${tripId}/travelers`), enabled: !!tripId })
}

export function usePlaces(tripId: string) {
  return useQuery({ queryKey: queryKeys.places(tripId), queryFn: () => api.get<Place[]>(`/trips/${tripId}/places`), enabled: !!tripId })
}

export function useItinerary(tripId: string) {
  return useQuery({ queryKey: queryKeys.itinerary(tripId), queryFn: () => api.get<ItineraryDay[]>(`/trips/${tripId}/itinerary`), enabled: !!tripId })
}

export function useExpenses(tripId: string, category = '') {
  const query = category ? `?category=${category}` : ''
  return useQuery({ queryKey: queryKeys.expenses(tripId, category), queryFn: () => api.get<Expense[]>(`/trips/${tripId}/expenses${query}`), enabled: !!tripId })
}

export function useBalances(tripId: string) {
  return useQuery({ queryKey: queryKeys.balances(tripId), queryFn: async () => (await api.get<{ balances: Balance[] }>(`/trips/${tripId}/balances`)).balances, enabled: !!tripId })
}

export function useSummary(tripId: string) {
  return useQuery({ queryKey: queryKeys.summary(tripId), queryFn: () => api.get<TripSummary>(`/trips/${tripId}/summary`), enabled: !!tripId })
}
