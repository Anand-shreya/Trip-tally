import { ArrowRight, BadgeIndianRupee, Sparkles, Trophy, UsersRound } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/ui'
import { formatMoney } from '../lib/format'
import { useSummary } from '../lib/queries'

export function SummaryPage() {
  const { id = '' } = useParams()
  const summary = useSummary(id)
  if (summary.isLoading) return <LoadingState label="Closing the books…" />
  if (summary.isError || !summary.data) return <ErrorState error={summary.error} retry={() => summary.refetch()} />
  const data = summary.data
  const categoryEntries = Object.entries(data.categories).sort((a, b) => Number(b[1]) - Number(a[1]))
  const maxCategory = Math.max(...categoryEntries.map(([, value]) => Number(value)), 1)
  return (
    <>
      <PageHeader title="Trip summary" intro={`${data.destination} · ${data.days} days`} />
      <section className="summary-hero"><div><span>Total spent</span><strong>{formatMoney(data.total_spent, data.currency)}</strong><p>{data.remaining === null ? 'No budget was set.' : Number(data.remaining) >= 0 ? `${formatMoney(data.remaining, data.currency)} under budget` : `${formatMoney(Math.abs(Number(data.remaining)), data.currency)} over budget`}</p></div><dl><div><dt>Budget</dt><dd>{data.budget ? formatMoney(data.budget, data.currency) : 'Open'}</dd></div><div><dt>Average / day</dt><dd>{formatMoney(data.average_per_day, data.currency)}</dd></div><div><dt>Largest expense</dt><dd>{data.most_expensive_expense ?? '—'}</dd></div></dl></section>
      <div className="summary-columns">
        <section className="summary-panel"><div className="panel-title"><BadgeIndianRupee /><h2>Spending map</h2></div>{categoryEntries.length ? <div className="bar-list">{categoryEntries.map(([category, value]) => <div key={category}><header><span>{category.toLowerCase()}</span><strong>{formatMoney(value, data.currency)}</strong></header><div className="bar-track"><span style={{ width: `${Number(value) / maxCategory * 100}%` }} /></div></div>)}</div> : <EmptyState title="No spending yet" message="Recorded expenses will appear here." />}</section>
        <section className="summary-panel"><div className="panel-title"><Trophy /><h2>Settle up</h2></div>{data.settlements.length ? <div className="settlement-list">{data.settlements.map((settlement, index) => <div key={`${settlement.from_traveler_id}-${settlement.to_traveler_id}-${index}`}><span>{settlement.from_traveler}</span><ArrowRight /><span>{settlement.to_traveler}</span><strong>{formatMoney(settlement.amount, data.currency)}</strong><p className="sr-only">{settlement.from_traveler} pays {settlement.to_traveler}</p></div>)}</div> : <p className="all-square">Everyone is square. No transfers needed.</p>}</section>
      </div>
      <section className="summary-panel summary-ledger">
        <div className="panel-title"><UsersRound /><h2>Traveler balances</h2></div>
        <div className="summary-ledger-list">{data.traveler_balances.map((balance) => {
          const net = Number(balance.net)
          return <article key={balance.traveler_id}><h3>{balance.traveler}</h3><span>Paid {formatMoney(balance.paid, data.currency)}</span><span>Share {formatMoney(balance.owed, data.currency)}</span><strong className={net >= 0 ? 'positive' : 'negative'}>Net {net > 0 ? '+' : ''}{formatMoney(net, data.currency)}</strong></article>
        })}</div>
      </section>
      <section className="ai-summary"><Sparkles /><div><h2>TripWise note</h2><p>{data.ai_summary}</p></div></section>
    </>
  )
}
