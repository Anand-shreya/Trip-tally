import { CloudSun, Droplets, Eye, Gauge, Sunrise, Sunset, Wind } from 'lucide-react'

import { formatDate } from '../../lib/format'
import type { DailyWeather, WeatherReport as WeatherReportData } from '../../lib/types'

function metric(value: string | number): string {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(Number(value))
}

function utcDateTime(value: string): string {
  const date = new Date(value)
  const day = new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
  const time = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }).format(date)
  return `${day}, ${time} UTC`
}

function utcTime(value: string): string {
  return `${new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }).format(new Date(value))} UTC`
}

function DailyRows({ rows }: { rows: DailyWeather[] }) {
  return (
    <div className="weather-daily-list">
      {rows.map((row) => (
        <article className="weather-day" key={`${row.requested_date}-${row.source}`}>
          <div>
            <strong>{formatDate(row.requested_date)}</strong>
            {row.source === 'historical' && <span>Based on {formatDate(row.source_date)}</span>}
          </div>
          <div><span>{row.condition}</span><strong>{metric(row.representative_c)}°C</strong></div>
          <dl>
            <div><dt>High / low</dt><dd>{metric(row.maximum_c)}° / {metric(row.minimum_c)}°</dd></div>
            <div><dt>Rain chance</dt><dd>{row.precipitation_probability_percent === null ? '—' : `${row.precipitation_probability_percent}%`}</dd></div>
            <div><dt>Rain</dt><dd>{row.precipitation_mm === null ? '—' : `${metric(row.precipitation_mm)} mm`}</dd></div>
            <div><dt>Humidity</dt><dd>{row.humidity_percent === null ? '—' : `${row.humidity_percent}%`}</dd></div>
            <div><dt>Wind</dt><dd>{metric(row.maximum_wind_kph)} km/h</dd></div>
          </dl>
        </article>
      ))}
    </div>
  )
}

export function WeatherReport({
  report,
  analyzedAt,
}: {
  report: WeatherReportData
  analyzedAt: string
}) {
  const current = report.current
  const forecast = report.daily.filter((row) => row.source === 'forecast')
  const historical = report.daily.filter((row) => row.source === 'historical')
  const sourceLabel = report.source === 'openweather'
    ? 'OpenWeather'
    : 'OpenWeather + Open-Meteo'

  return (
    <section className="weather-report" aria-label="Weather report">
      <header className="report-heading">
        <div>
          <span className="report-icon"><CloudSun /></span>
          <div><h2>{report.location.name}, {report.location.country_code}</h2><p>{report.summary}</p></div>
        </div>
        <span className="source-badge">{sourceLabel}</span>
      </header>

      <article className="weather-observation">
        <div className="weather-temperature">
          <span>{current.condition}</span>
          <strong>{metric(current.temperature_c)}°C</strong>
          <p>Feels like {metric(current.feels_like_c)}°C</p>
          <small>Observed {utcDateTime(current.observed_at)}</small>
        </div>
        <dl className="weather-details">
          <div><CloudSun /><dt>High / low</dt><dd>{metric(current.maximum_c)}°C / {metric(current.minimum_c)}°C</dd></div>
          <div><Droplets /><dt>Humidity</dt><dd>{current.humidity_percent}%</dd></div>
          <div><Gauge /><dt>Pressure</dt><dd>{current.pressure_hpa.toLocaleString('en-IN')} hPa</dd></div>
          <div><Eye /><dt>Visibility</dt><dd>{metric(current.visibility_m / 1000)} km</dd></div>
          <div><CloudSun /><dt>Cloud cover</dt><dd>{current.cloud_percent}%</dd></div>
          <div><Wind /><dt>Wind</dt><dd>{metric(current.wind_speed_kph)} km/h · {current.wind_direction_degrees}°</dd></div>
          <div><Sunrise /><dt>Sunrise</dt><dd>{utcTime(current.sunrise_at)}</dd></div>
          <div><Sunset /><dt>Sunset</dt><dd>{utcTime(current.sunset_at)}</dd></div>
        </dl>
      </article>

      {forecast.length > 0 && (
        <section className="weather-period">
          <h3>Forecast for your dates</h3>
          <p>Provider forecast mapped to your requested travel dates.</p>
          <DailyRows rows={forecast} />
        </section>
      )}
      {historical.length > 0 && (
        <section className="weather-period historical-weather">
          <h3>Typical weather from recent history</h3>
          <p>Recent matching dates are shown when future forecast data is unavailable.</p>
          <DailyRows rows={historical} />
        </section>
      )}
      <footer>Analysis updated {utcDateTime(analyzedAt)}</footer>
    </section>
  )
}
