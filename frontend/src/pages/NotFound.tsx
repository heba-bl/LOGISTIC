import { Link } from 'react-router-dom'
import { MapPinOff } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="panel flex flex-col items-center gap-4 px-6 py-20 text-center">
      <MapPinOff className="h-8 w-8 text-ink-3" strokeWidth={1.6} />
      <div>
        <p className="numeric text-2xl font-semibold text-ink">404</p>
        <p className="mt-1 text-xs text-ink-2">This route is not part of the control center.</p>
      </div>
      <Link
        to="/mission-control"
        className="rounded-lg border border-accent/30 bg-accent-dim px-3 py-2 text-xs font-medium text-accent transition-colors hover:border-accent/60"
      >
        Back to Mission Control
      </Link>
    </div>
  )
}
