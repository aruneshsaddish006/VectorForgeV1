import * as React from "react"
import { cn } from "@/lib/utils"
import { StatusPill } from "@/components/ui/status-pill"
import type { AgentStatus } from "@/lib/types"

export function AgentCard({
  title,
  status,
  icon: Icon,
  source,
  children,
  className,
}: {
  title: string
  status: AgentStatus
  icon: React.ElementType
  source?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        "w-full overflow-hidden rounded-xl border border-border bg-surface shadow-sm",
        className,
      )}
      aria-label={title}
    >
      <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-info-soft text-primary">
            <Icon className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold leading-tight text-foreground text-pretty">
              {title}
            </h3>
            {source && (
              <p className="mt-0.5 text-xs text-muted-foreground">{source}</p>
            )}
          </div>
        </div>
        <StatusPill status={status} className="shrink-0" />
      </header>
      <div className="px-4 py-4 sm:px-5">{children}</div>
    </section>
  )
}

export function MetricBlock({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string
  value: string
  hint?: string
  tone?: "default" | "success" | "warning" | "primary"
}) {
  const toneClass = {
    default: "text-foreground",
    success: "text-success",
    warning: "text-warning",
    primary: "text-primary",
  }[tone]
  return (
    <div className="rounded-lg border border-border bg-surface-muted/60 px-3 py-2.5">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-lg font-semibold tabular-nums leading-none", toneClass)}>
        {value}
      </div>
      {hint && <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}
