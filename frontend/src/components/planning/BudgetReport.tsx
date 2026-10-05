import { BadgeIndianRupee, Plane } from 'lucide-react'

import { formatMoney } from '../../lib/format'
import type { BudgetReport as BudgetReportData, EstimateRange } from '../../lib/types'

const categories: Array<{
  key: keyof BudgetReportData['categories']
  label: string
}> = [
  { key: 'flights', label: 'Round-trip flights' },
  { key: 'accommodation', label: 'Accommodation' },
  { key: 'food', label: 'Food' },
  { key: 'local_transport', label: 'Local transport' },
  { key: 'tickets', label: 'Tickets' },
  { key: 'activities', label: 'Activities' },
]

function categoryLabel(
  key: keyof BudgetReportData['categories'],
  label: string,
  travelerCount: number,
): string {
  if (key !== 'flights') return label
  const travelers = travelerCount === 1 ? 'traveler' : 'travelers'
  return `Round-trip economy flights · ${travelerCount} ${travelers}`
}

function MoneyCells({ range, currency }: { range: EstimateRange; currency: string }) {
  return (
    <>
      <td>{formatMoney(range.minimum, currency)}</td>
      <td><strong>{formatMoney(range.typical, currency)}</strong></td>
      <td>{formatMoney(range.maximum, currency)}</td>
    </>
  )
}

export function BudgetReport({
  report,
  model,
}: {
  report: BudgetReportData
  model: string
}) {
  return (
    <section className="budget-report" aria-label="Trip budget estimate">
      <header className="report-heading">
        <div>
          <span className="report-icon budget-icon"><BadgeIndianRupee /></span>
          <div><h2>Trip budget</h2><p>{report.traveler_count} {report.traveler_count === 1 ? 'traveler' : 'travelers'} · {report.number_of_days} days</p></div>
        </div>
        <span className="source-badge gemini-badge">{model}</span>
      </header>
      <div className="budget-total">
        <span>Typical group total</span>
        <strong>{formatMoney(report.total.typical, report.currency)}</strong>
        <p>{formatMoney(report.total.minimum, report.currency)} – {formatMoney(report.total.maximum, report.currency)}</p>
      </div>
      <div className="budget-table-wrap">
        <table className="budget-table">
          <thead><tr><th scope="col">Category</th><th scope="col">Minimum</th><th scope="col">Typical</th><th scope="col">Maximum</th></tr></thead>
          <tbody>
            {categories.map(({ key, label }) => (
              <tr key={key}>
                <th scope="row">{key === 'flights' && <Plane size={16} />} {categoryLabel(key, label, report.traveler_count)}</th>
                <MoneyCells range={report.categories[key]} currency={report.currency} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer>Gemini estimate—not a live quote</footer>
    </section>
  )
}
