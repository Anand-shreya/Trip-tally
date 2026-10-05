export type TravelStyle = 'BUDGET' | 'COMFORTABLE' | 'PREMIUM'
export type TripStatus = 'DRAFT' | 'PLANNING' | 'READY' | 'ACTIVE' | 'COMPLETED'
export type ExpenseCategory = 'FOOD' | 'ACCOMMODATION' | 'TRANSPORT' | 'ACTIVITIES' | 'TICKETS' | 'SHOPPING' | 'OTHER'

export interface Traveler {
  id: string
  name: string
  email: string | null
  created_at: string
}

export interface Trip {
  id: string
  name: string
  departure_city: string | null
  destination: string
  start_date: string
  end_date: string
  number_of_days: number
  base_currency: string
  budget: string | null
  travel_style: TravelStyle
  status: TripStatus
  is_archived: boolean
  archived_at: string | null
  weather_score: string | null
  weather_rating: string | null
  weather_summary: string | null
  estimated_cost_min: string | null
  estimated_cost: string | null
  estimated_cost_max: string | null
  travelers: Traveler[]
  created_at: string
  updated_at: string
}

export interface Place {
  id: string
  name: string
  description: string
  latitude: number
  longitude: number
  recommended_days: string
  relevance_score: string
  best_for: string[]
  selected: boolean
}

export interface ResolvedLocation {
  name: string
  country_code: string
  latitude: number
  longitude: number
  timezone_offset_seconds: number
}

export interface CurrentWeather {
  observed_at: string
  condition: string
  description: string
  temperature_c: string
  feels_like_c: string
  minimum_c: string
  maximum_c: string
  humidity_percent: number
  pressure_hpa: number
  visibility_m: number
  cloud_percent: number
  wind_speed_kph: string
  wind_direction_degrees: number
  rain_mm_1h: string | null
  snow_mm_1h: string | null
  sunrise_at: string
  sunset_at: string
}

export interface DailyWeather {
  requested_date: string
  source_date: string
  source: 'forecast' | 'historical'
  minimum_c: string
  maximum_c: string
  representative_c: string
  condition: string
  precipitation_probability_percent: number | null
  precipitation_mm: string | null
  humidity_percent: number | null
  maximum_wind_kph: string
}

export interface WeatherReport {
  location: ResolvedLocation
  current: CurrentWeather
  daily: DailyWeather[]
  source: 'openweather' | 'openweather+open-meteo'
  summary: string
}

export interface EstimateRange {
  minimum: string
  typical: string
  maximum: string
}

export interface BudgetReport {
  currency: string
  traveler_count: number
  number_of_days: number
  categories: {
    flights: EstimateRange
    accommodation: EstimateRange
    food: EstimateRange
    local_transport: EstimateRange
    tickets: EstimateRange
    activities: EstimateRange
  }
  total: EstimateRange
}

export interface PlanningAnalysis {
  weather: WeatherReport
  budget: BudgetReport
  places: Place[]
  weather_source: string
  budget_model: string
  analyzed_at: string
  status: string
}

export interface ItineraryActivity {
  id: string
  title: string
  description: string
  activity_type: string
  start_time: string
  end_time: string
  location_name: string
  latitude: number | null
  longitude: number | null
  estimated_cost: string
}

export interface ItineraryDay {
  id: string
  day_number: number
  date: string
  title: string
  summary: string
  activities: ItineraryActivity[]
}

export interface ExpenseSplit { id: string; traveler_id: string; share_amount: string }
export interface Expense {
  id: string
  trip_id: string
  description: string
  amount: string
  currency: string
  exchange_rate: string
  base_amount: string
  category: ExpenseCategory
  paid_by: string
  expense_date: string
  location: string | null
  notes: string | null
  created_at: string
  splits: ExpenseSplit[]
}

export interface Balance {
  traveler_id: string
  traveler: string
  paid: string
  owed: string
  net: string
}

export interface Settlement {
  from_traveler_id: string
  from_traveler: string
  to_traveler_id: string
  to_traveler: string
  amount: string
}

export interface TripSummary {
  trip_id: string
  trip_name: string
  destination: string
  days: number
  currency: string
  budget: string | null
  total_spent: string
  remaining: string | null
  average_per_day: string
  categories: Record<string, string>
  most_expensive_category: string | null
  most_expensive_expense: string | null
  traveler_balances: Balance[]
  settlements: Settlement[]
  ai_summary: string
}

export interface Job {
  id: string
  trip_id: string
  type: string
  status: string
  attempt: number
  max_attempts: number
  result: Record<string, unknown> | null
  error: string | null
}

export interface AIProviderStatus {
  provider: 'gemini' | 'local'
  label: string
  model: string | null
  ai_enabled: boolean
}

export type ChatGPTConnectionState =
  | 'disconnected'
  | 'connected'
  | 'scope_required'
  | 'model_required'

export interface ChatGPTStatus {
  state: ChatGPTConnectionState
  signed_in: boolean
  plan_enabled: boolean
  name: string | null
  email: string | null
  models: string[]
  selected_model: string | null
  manage_usage_url: string
}
