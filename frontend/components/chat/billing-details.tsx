"use client"

import * as React from "react"
import {
  ArrowUpRight,
  Check,
  CreditCard,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  createBillingCheckout,
  createBillingPortal,
  fetchBillingSummary,
  type BillingPlan,
  type BillingSummary,
  type BillingUsageItem,
  type Workspace,
} from "@/lib/api"
import { cn } from "@/lib/utils"

export function BillingDetails({ selectedWorkspace }: { selectedWorkspace: Workspace | null }) {
  const [summary, setSummary] = React.useState<BillingSummary | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [actionPlan, setActionPlan] = React.useState<string | null>(null)
  const [portalLoading, setPortalLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const loadBilling = React.useCallback(async () => {
    if (!selectedWorkspace) {
      setSummary(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setSummary(await fetchBillingSummary(selectedWorkspace.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load billing details.")
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspace?.id])

  React.useEffect(() => {
    loadBilling()
  }, [loadBilling])

  async function handleCheckout(planId: string) {
    if (!selectedWorkspace) return
    setActionPlan(planId)
    setError(null)
    try {
      const session = await createBillingCheckout({ workspaceId: selectedWorkspace.id, plan: planId })
      window.location.href = session.url
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start Stripe checkout.")
    } finally {
      setActionPlan(null)
    }
  }

  async function handlePortal() {
    if (!selectedWorkspace) return
    setPortalLoading(true)
    setError(null)
    try {
      const session = await createBillingPortal({ workspaceId: selectedWorkspace.id })
      window.location.href = session.url
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open Stripe billing portal.")
    } finally {
      setPortalLoading(false)
    }
  }

  if (!selectedWorkspace) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="app-panel-raised max-w-2xl rounded-[28px] p-8 text-center">
          <CreditCard className="mx-auto h-8 w-8 text-primary" aria-hidden="true" />
          <h1 className="mt-4 font-heading text-3xl font-bold">Select a workspace</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Billing, subscription, and usage are scoped to a workspace.
          </p>
        </div>
      </div>
    )
  }

  const activePlan = summary?.subscription.plan ?? "free"
  const activePlanDetails = summary?.plans.find((plan) => plan.id === activePlan)

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <section className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <div className="app-panel-raised rounded-[30px] p-6 sm:p-8">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Billing</p>
                <h1 className="mt-3 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                  Subscription
                </h1>
              </div>
              <div className="rounded-2xl bg-surface-muted px-4 py-3 text-right">
                <div className="text-xs font-medium text-muted-foreground">Month-to-date spend</div>
                <div className="mt-1 text-3xl font-bold tabular-nums text-foreground">
                  {loading ? "..." : formatCurrency(summary?.usage.periodSpend ?? 0)}
                </div>
              </div>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <StatusTile label="Workspace" value={selectedWorkspace.name} icon={ShieldCheck} />
              <StatusTile label="Current plan" value={activePlanDetails?.name ?? activePlan} icon={CreditCard} />
              <StatusTile
                label="Subscription status"
                value={summary?.subscription.status ?? "Loading"}
                icon={Sparkles}
              />
            </div>
          </div>

          <div className="app-panel-raised rounded-[30px] p-6">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-info-soft text-info">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <div className="text-sm font-bold text-foreground">{selectedWorkspace.name}</div>
                <div className="text-sm text-muted-foreground">
                  Plan: <span className="font-bold capitalize text-foreground">{activePlan}</span>
                </div>
              </div>
            </div>
            <div className="mt-5 grid gap-2">
              <Button variant="outline" onClick={loadBilling} disabled={loading} className="justify-start rounded-2xl">
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
                Refresh usage
              </Button>
              <Button variant="secondary" onClick={handlePortal} disabled={portalLoading} className="justify-start rounded-2xl">
                {portalLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
                Manage in Stripe
              </Button>
            </div>
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}

        <PlanPanel
          plans={summary?.plans ?? []}
          activePlan={activePlan}
          actionPlan={actionPlan}
          onCheckout={handleCheckout}
          loading={loading}
        />

        <UsagePanel summary={summary} loading={loading} />
      </div>
    </div>
  )
}

function StatusTile({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: React.ElementType
}) {
  return (
    <div className="app-control rounded-2xl p-4">
      <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
      <div className="mt-3 text-xs font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-lg font-bold capitalize text-foreground">{value}</div>
    </div>
  )
}

function PlanPanel({
  plans,
  activePlan,
  actionPlan,
  onCheckout,
  loading,
}: {
  plans: BillingPlan[]
  activePlan: string
  actionPlan: string | null
  onCheckout: (planId: string) => void
  loading: boolean
}) {
  const displayPlans = plans.length > 0 ? plans : fallbackPlans()
  return (
    <section className="app-panel-raised rounded-[28px] p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-heading text-2xl font-bold">Plans</h2>
          <p className="mt-1 text-sm text-muted-foreground">Choose the workspace subscription that matches your usage.</p>
        </div>
        <span className="w-fit rounded-full bg-info-soft px-3 py-1 text-xs font-bold text-info">Stripe enabled</span>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {displayPlans.map((plan) => {
          const active = plan.id === activePlan
          const highlighted = plan.id === "pro"
          const canCheckout = plan.id !== "free"
          return (
            <article
              key={plan.id}
              className={cn(
                "flex min-h-[18rem] flex-col rounded-2xl border p-4 transition",
                highlighted ? "border-primary bg-primary text-primary-foreground shadow-sm" : "border-primary/60 bg-surface",
                active && !highlighted && "ring-2 ring-primary/30",
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className={cn("flex items-center gap-2 text-xl font-bold", highlighted ? "text-white" : "text-primary")}>
                    {plan.name}
                    {active && (
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px]", highlighted ? "bg-white/20 text-white" : "bg-info-soft text-info")}>
                        Current
                      </span>
                    )}
                  </div>
                  <p className={cn("mt-2 text-sm font-medium", highlighted ? "text-white" : "text-foreground")}>{plan.summary}</p>
                </div>
                <div className={cn("text-right text-2xl font-bold", highlighted ? "text-white" : "text-foreground")}>
                  ${plan.priceMonthly}
                  {plan.priceMonthly > 0 && <span className="text-base"> / mo</span>}
                </div>
              </div>
              <ul className={cn("mt-3 flex flex-wrap gap-2 text-xs", highlighted ? "text-white" : "text-muted-foreground")}>
                {plan.features.map((feature) => (
                  <li key={feature} className={cn("inline-flex items-center gap-1 rounded-full px-2 py-1", highlighted ? "bg-white/15" : "bg-surface-muted")}>
                    <Check className="h-3 w-3" aria-hidden="true" />
                    {feature}
                  </li>
                ))}
              </ul>
              <div className="flex-1" />
              {canCheckout && (
                <div className="mt-4">
                  <Button
                    variant={highlighted ? "secondary" : "primary"}
                    size="sm"
                    onClick={() => onCheckout(plan.id)}
                    disabled={loading || actionPlan === plan.id || active || !plan.checkoutEnabled}
                    className={highlighted ? "bg-white text-primary hover:bg-white/90" : undefined}
                  >
                    {actionPlan === plan.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
                    {active ? "Current plan" : plan.checkoutEnabled ? "Subscribe with Stripe" : "Stripe price not configured"}
                    {!active && plan.checkoutEnabled && <ArrowUpRight className="h-4 w-4" />}
                  </Button>
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function UsagePanel({ summary, loading }: { summary: BillingSummary | null; loading: boolean }) {
  return (
    <section className="app-panel-raised rounded-[28px] p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-heading text-2xl font-bold">Current subscription usage</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {summary
              ? `Billing period started ${formatDate(summary.subscription.currentPeriodStart)}.`
              : "Usage appears after the billing summary loads."}
          </p>
        </div>
        <div className="app-control rounded-2xl px-4 py-3 text-right">
          <div className="text-xs font-medium text-muted-foreground">Month-to-date spend</div>
          <div className="text-2xl font-bold text-foreground">{loading ? "..." : formatCurrency(summary?.usage.periodSpend ?? 0)}</div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {(summary?.usage.items ?? fallbackUsage()).map((item) => (
          <UsageMeter key={item.key} item={item} loading={loading} />
        ))}
      </div>

      <div className="mt-5 rounded-2xl border border-border bg-surface-muted/60 p-4">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-info-soft text-info">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-foreground">Stripe usage approval pattern</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Subscription entitlements are enforced before paid actions. Metered overages can route through a
              human approval card before charging through Stripe.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

function UsageMeter({ item, loading }: { item: BillingUsageItem; loading: boolean }) {
  const unlimited = item.limit === null
  const percent = unlimited ? 18 : Math.min(100, Math.round((item.value / Math.max(item.limit || 1, 1)) * 100))
  return (
    <article className="app-control rounded-2xl p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-foreground">{item.label}</h3>
          <p className="mt-1 min-h-10 text-xs leading-5 text-muted-foreground">{item.description}</p>
        </div>
      </div>
      <div className="mt-4 flex items-end justify-between">
        <div className="text-2xl font-bold tabular-nums text-foreground">{loading ? "..." : formatUsageValue(item.value)}</div>
        <div className="text-xs font-semibold text-muted-foreground">{unlimited ? "Unlimited" : `of ${item.limit}`}</div>
      </div>
      <div className="mt-3 h-2 rounded-full bg-surface-muted">
        <div className={cn("h-full rounded-full", percent > 85 ? "bg-warning" : "bg-primary")} style={{ width: `${percent}%` }} />
      </div>
    </article>
  )
}

function fallbackPlans(): BillingPlan[] {
  return [
    { id: "free", name: "Free", priceMonthly: 0, summary: "Try one use case end-to-end", features: ["1 use case"], limits: {}, checkoutEnabled: false },
    { id: "pro", name: "Pro", priceMonthly: 49, summary: "3 use cases · 10 Exa datasets · 5 RAG trials", features: ["Stripe subscription", "Usage approvals"], limits: {}, checkoutEnabled: false },
    { id: "enterprise", name: "Enterprise", priceMonthly: 299, summary: "Unlimited · custom models · SLA", features: ["Custom models", "SLA"], limits: {}, checkoutEnabled: false },
  ]
}

function fallbackUsage(): BillingUsageItem[] {
  return [
    { key: "useCases", label: "Use cases", value: 0, limit: 1, unit: "count", description: "Generated use cases in this workspace" },
    { key: "exaDatasets", label: "Exa datasets", value: 0, limit: 0, unit: "count", description: "Web datasets built or enriched" },
    { key: "ragTrials", label: "RAG trials", value: 0, limit: 0, unit: "count", description: "AutoRAG optimization trials" },
    { key: "trainingRuns", label: "Training runs", value: 0, limit: 1, unit: "runs", description: "AutoGluon/model training jobs" },
  ]
}

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })
  } catch {
    return value
  }
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
}

function formatUsageValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}
