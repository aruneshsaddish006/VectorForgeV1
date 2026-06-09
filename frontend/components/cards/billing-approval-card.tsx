import { CreditCard, AlertTriangle } from "lucide-react"
import { AgentCard } from "./agent-card"
import { Button } from "@/components/ui/button"

const LINE_ITEMS = [
  { label: "Exa Agent dataset build (medium effort)", value: "$0.10" },
  { label: "AutoGluon training — 6m 24s @ $0.10/min", value: "$0.64" },
  { label: "AutoRAG — 24 trials @ $0.05/trial", value: "$1.20" },
]

export function BillingApprovalCard() {
  return (
    <AgentCard
      title="Stripe Usage Approval Required"
      status="waiting-approval"
      icon={CreditCard}
      source="Billing Agent · metered usage on Pro plan"
    >
      <p className="text-sm leading-relaxed text-foreground">
        This session used pay-per-use compute beyond your monthly allowance. Review and approve the charge
        to continue.
      </p>

      <div className="mt-4 overflow-hidden rounded-lg border border-border">
        <ul className="divide-y divide-border">
          {LINE_ITEMS.map((item) => (
            <li key={item.label} className="flex items-center justify-between gap-3 px-3 py-2.5 text-[13px]">
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-mono font-medium tabular-nums text-foreground">{item.value}</span>
            </li>
          ))}
          <li className="flex items-center justify-between gap-3 bg-surface-muted/60 px-3 py-2.5">
            <span className="text-sm font-semibold text-foreground">Total due</span>
            <span className="font-mono text-base font-semibold tabular-nums text-foreground">$1.94</span>
          </li>
        </ul>
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning-soft/50 px-3 py-2 text-[13px] text-foreground">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
        <span>Charged to Visa ending 4242. Exa usage is passed through at cost with no markup.</span>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
        <Button variant="success">Approve Stripe Charge — $1.94</Button>
        <Button variant="outline">Upgrade to Enterprise</Button>
        <Button variant="ghost">Cancel</Button>
      </div>
    </AgentCard>
  )
}
