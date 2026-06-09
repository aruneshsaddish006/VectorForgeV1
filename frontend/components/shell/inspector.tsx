"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { STATUS_META } from "@/lib/status"
import { fetchDemoWorkspace } from "@/lib/api"
import type { ActivityEntry, SchemaColumn } from "@/lib/types"
import { Database, Cpu, FileCheck2, DollarSign } from "lucide-react"

type Tab = "context" | "schema" | "activity"

const ACTIVITY: ActivityEntry[] = [
  {
    id: "a7",
    agent: "Billing Agent",
    message: "Awaiting Stripe charge approval — $1.94",
    time: "now",
    status: "waiting-approval",
    tool: "Stripe API",
    cost: "$1.94",
    detail: "Pay-per-use overage on Pro plan.",
  },
  {
    id: "a6",
    agent: "RAG Agent",
    message: "Completed 24 pipeline trials",
    time: "2m ago",
    status: "complete",
    tool: "AutoRAG",
    detail: "Best config: hybrid retriever + cohere rerank.",
  },
  {
    id: "a5",
    agent: "Training Agent",
    message: "AutoGluon job finished — ROC-AUC 0.921",
    time: "8m ago",
    status: "complete",
    tool: "SageMaker",
    cost: "$0.64",
  },
  {
    id: "a4",
    agent: "Data Agent",
    message: "Dataset schema confirmed by approver",
    time: "12m ago",
    status: "complete",
    tool: "S3",
  },
  {
    id: "a3",
    agent: "Data Agent",
    message: "Exa run completed — 180 rows validated",
    time: "15m ago",
    status: "complete",
    tool: "Exa Agent API",
    cost: "$0.10",
    detail: "Grounding citations stored for 6 fields.",
  },
  {
    id: "a2",
    agent: "Strategy Agent",
    message: "Generated AI strategy + ROI map",
    time: "19m ago",
    status: "complete",
    tool: "LLM",
  },
  {
    id: "a1",
    agent: "Intent Agent",
    message: "Classified intent as Classification",
    time: "21m ago",
    status: "complete",
    tool: "LLM",
  },
]

const SCHEMA: SchemaColumn[] = [
  { name: "company", type: "string", nullPct: 0, sample: "Northwind SaaS", source: "exa" },
  { name: "arr_usd", type: "number", nullPct: 2, sample: "4,200,000", source: "exa" },
  { name: "employee_count", type: "integer", nullPct: 0, sample: "180", source: "exa" },
  { name: "nps_score", type: "number", nullPct: 8, sample: "41", source: "enriched" },
  { name: "support_tickets", type: "integer", nullPct: 4, sample: "312", source: "enriched" },
  { name: "churned", type: "boolean", nullPct: 0, sample: "false", source: "exa" },
]

export function Inspector({ open }: { open: boolean }) {
  const [tab, setTab] = React.useState<Tab>("context")
  const [activity, setActivity] = React.useState<ActivityEntry[]>(ACTIVITY)
  const [schema, setSchema] = React.useState<SchemaColumn[]>(SCHEMA)

  React.useEffect(() => {
    const controller = new AbortController()

    fetchDemoWorkspace(controller.signal)
      .then((data) => {
        setActivity(data.activity)
        setSchema(data.dataset.columns)
      })
      .catch(() => {
        setActivity(ACTIVITY)
        setSchema(SCHEMA)
      })

    return () => controller.abort()
  }, [])

  if (!open) return null

  return (
    <aside
      className="app-panel hidden w-80 shrink-0 flex-col overflow-hidden rounded-[28px] xl:flex"
      aria-label="Context inspector"
    >
      <div className="flex h-16 items-center border-b border-border px-3">
        <nav className="flex w-full gap-1" role="tablist" aria-label="Inspector views">
          {(["context", "schema", "activity"] as Tab[]).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={cn(
                "flex-1 rounded-full px-2 py-2 text-xs font-semibold capitalize transition-colors",
                tab === t ? "bg-surface-raised text-foreground shadow-sm" : "text-muted-foreground hover:bg-surface-raised/70",
              )}
            >
              {t}
            </button>
          ))}
        </nav>
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto p-4">
        {tab === "context" && <ContextView />}
        {tab === "schema" && <SchemaView schema={schema} />}
        {tab === "activity" && <ActivityView activity={activity} />}
      </div>
    </aside>
  )
}

function ContextView() {
  const items = [
    { icon: FileCheck2, label: "Use case", value: "Churn Prediction" },
    { icon: Cpu, label: "Task type", value: "Classification" },
    { icon: Database, label: "Dataset", value: "saas_churn_v2 · 180 rows" },
    { icon: DollarSign, label: "Session cost", value: "$1.94" },
  ]
  return (
    <div className="space-y-4">
      <div>
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Current context
        </h4>
        <div className="space-y-2">
          {items.map((i) => {
            const Icon = i.icon
            return (
              <div key={i.label} className="app-control flex items-center gap-3 rounded-2xl px-3 py-2">
                <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="min-w-0">
                  <div className="text-[11px] text-muted-foreground">{i.label}</div>
                  <div className="truncate text-[13px] font-medium text-foreground">{i.value}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div>
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          KPIs
        </h4>
        <div className="app-control rounded-2xl p-3 text-[13px] leading-relaxed text-foreground">
          Reduce logo churn by 15% over two quarters by flagging at-risk accounts 90 days in advance.
        </div>
      </div>

      <div>
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Pending approvals
        </h4>
        <div className="flex items-center justify-between rounded-2xl border border-warning/30 bg-warning-soft/50 px-3 py-2 text-[13px] shadow-sm">
          <span className="text-foreground">Stripe charge</span>
          <span className="font-mono font-medium text-warning">$1.94</span>
        </div>
      </div>
    </div>
  )
}

function SchemaView({ schema }: { schema: SchemaColumn[] }) {
  const sourceStyle: Record<string, string> = {
    uploaded: "bg-surface-muted text-muted-foreground",
    exa: "bg-info-soft text-primary",
    enriched: "bg-success-soft text-success",
  }
  return (
    <div>
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        saas_churn_v2 · 6 columns
      </h4>
      <ul className="space-y-1.5">
        {schema.map((c) => (
          <li key={c.name} className="app-control flex items-center justify-between gap-2 rounded-2xl px-3 py-2">
            <div className="min-w-0">
              <div className="truncate font-mono text-[13px] font-medium text-foreground">{c.name}</div>
              <div className="font-mono text-[11px] text-muted-foreground">{c.type}</div>
            </div>
            <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium capitalize", sourceStyle[c.source])}>
              {c.source}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ActivityView({ activity }: { activity: ActivityEntry[] }) {
  return (
    <div>
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Agent activity log
      </h4>
      <ol className="relative space-y-3 border-l border-border pl-4">
        {activity.map((e) => (
          <ActivityItem key={e.id} entry={e} />
        ))}
      </ol>
    </div>
  )
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  const [open, setOpen] = React.useState(false)
  const meta = STATUS_META[entry.status]
  const Icon = meta.icon
  return (
    <li className="relative">
      <span
        className={cn(
          "absolute -left-[1.42rem] top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-surface",
          meta.accent,
        )}
      >
        <Icon className={cn("h-3.5 w-3.5", meta.spin && "animate-spin")} aria-hidden="true" />
      </span>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left"
        aria-expanded={open}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold text-foreground">{entry.agent}</span>
          <span className="shrink-0 text-[10px] text-muted-foreground">{entry.time}</span>
        </div>
        <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground">{entry.message}</p>
      </button>
      {open && (entry.tool || entry.cost || entry.detail) && (
        <div className="app-control mt-1.5 space-y-1 rounded-2xl px-2.5 py-2 text-[11px] text-muted-foreground">
          {entry.tool && (
            <div className="flex justify-between">
              <span>Tool</span>
              <span className="font-medium text-foreground">{entry.tool}</span>
            </div>
          )}
          {entry.cost && (
            <div className="flex justify-between">
              <span>Cost</span>
              <span className="font-mono font-medium text-foreground">{entry.cost}</span>
            </div>
          )}
          {entry.detail && <p className="pt-0.5 leading-snug">{entry.detail}</p>}
        </div>
      )}
    </li>
  )
}
