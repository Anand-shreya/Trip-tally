export const queryKeys = {
  aiProvider: ['ai', 'provider-status'] as const,
  chatgpt: ['chatgpt', 'status'] as const,
  trips: ['trips'] as const,
  trip: (tripId: string) => ['trips', tripId] as const,
  analysis: (tripId: string) => ['trips', tripId, 'analysis'] as const,
  travelers: (tripId: string) => ['trips', tripId, 'travelers'] as const,
  places: (tripId: string) => ['trips', tripId, 'places'] as const,
  itinerary: (tripId: string) => ['trips', tripId, 'itinerary'] as const,
  expenses: (tripId: string, filters = '') => ['trips', tripId, 'expenses', filters] as const,
  balances: (tripId: string) => ['trips', tripId, 'balances'] as const,
  summary: (tripId: string) => ['trips', tripId, 'summary'] as const,
}
