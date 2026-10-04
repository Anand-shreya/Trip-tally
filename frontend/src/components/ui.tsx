import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { AlertCircle, LoaderCircle, MapPin } from 'lucide-react'

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} {...props} />
}

export function PageHeader({ title, intro, action }: { title: string; intro?: string; action?: ReactNode }) {
  return (
    <header className="page-header">
      <div><h1>{title}</h1>{intro && <p>{intro}</p>}</div>
      {action}
    </header>
  )
}

export function LoadingState({ label = 'Plotting the route…' }: { label?: string }) {
  return <div className="state-panel" role="status"><LoaderCircle className="spin" /> <span>{label}</span></div>
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something interrupted this route.'
  return (
    <div className="state-panel state-panel-error" role="alert">
      <AlertCircle />
      <div><strong>Couldn’t load this stop</strong><p>{message}</p></div>
      {retry && <Button onClick={retry}>Try again</Button>}
    </div>
  )
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return <div className="empty-state"><MapPin /><h2>{title}</h2><p>{message}</p>{action}</div>
}

export function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()}>
        <header><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog">×</button></header>
        {children}
      </section>
    </div>
  )
}
