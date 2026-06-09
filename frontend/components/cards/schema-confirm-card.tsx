"use client"

import * as React from "react"
import { Table2, Play, Wrench, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { AgentCard } from "./agent-card"
import { Button } from "@/components/ui/button"
import type { DatasetSchema, SchemaColumn } from "@/lib/types"

const COLUMNS: SchemaColumn[] = [
  { name: "company", type: "string", nullPct: 0, sample: "Northwind SaaS", source: "exa" },
  { name: "arr_usd", type: "number", nullPct: 2, sample: "4,200,000", source: "exa" },
  { name: "employee_count", type: "integer", nullPct: 0, sample: "180", source: "exa" },
  { name: "nps_score", type: "number", nullPct: 8, sample: "41", source: "enriched" },
  { name: "support_tickets", type: "integer", nullPct: 4, sample: "312", source: "enriched" },
  { name: "churned", type: "boolean", nullPct: 0, sample: "false", source: "exa" },
]

const DEFAULT_DATASET: DatasetSchema = {
  id: "saas_churn_v2",
  name: "saas_churn_v2",
  rowCount: 180,
  columnCount: 6,
  taskType: "Classification",
  qualityScore: 92,
  targetColumn: "churned",
  columns: COLUMNS,
  issues: [
    {
      field: "nps_score",
      message:
        "nps_score has 8% nulls. The agent can impute with the median or drop affected rows.",
    },
  ],
}

const SOURCE_STYLE: Record<SchemaColumn["source"], string> = {
  uploaded: "bg-surface-muted text-muted-foreground",
  exa: "bg-info-soft text-primary",
  enriched: "bg-success-soft text-success",
}

const TYPE_STYLE: Record<SchemaColumn["type"], string> = {
  string: "text-foreground",
  number: "text-primary",
  integer: "text-primary",
  boolean: "text-warning",
}

export function SchemaConfirmCard({ dataset = DEFAULT_DATASET }: { dataset?: DatasetSchema }) {
  const [target, setTarget] = React.useState(dataset.targetColumn)
  return (
    <AgentCard
      title="Confirm dataset schema before training"
      status="waiting-approval"
      icon={Table2}
      source="Data Agent · final approval gate before AutoGluon"
    >
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <Mini label="Rows" value={String(dataset.rowCount)} />
        <Mini label="Columns" value={String(dataset.columnCount)} />
        <Mini label="Task type" value={dataset.taskType} />
        <Mini label="Quality score" value={`${dataset.qualityScore} / 100`} tone="success" />
      </div>

      <div className="mt-4 scroll-thin overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[600px] text-left text-[13px]">
          <thead className="bg-surface-muted text-[11px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Column</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Null %</th>
              <th className="px-3 py-2 font-medium">Sample</th>
              <th className="px-3 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {dataset.columns.map((c) => (
              <tr key={c.name} className="hover:bg-surface-muted/50">
                <td className="px-3 py-2 font-mono font-medium text-foreground">{c.name}</td>
                <td className={cn("px-3 py-2 font-mono", TYPE_STYLE[c.type])}>{c.type}</td>
                <td className="px-3 py-2">
                  <span
                    className={cn(
                      "tabular-nums",
                      c.nullPct >= 8 ? "font-medium text-warning" : "text-muted-foreground",
                    )}
                  >
                    {c.nullPct}%
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-muted-foreground">{c.sample}</td>
                <td className="px-3 py-2">
                  <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium capitalize", SOURCE_STYLE[c.source])}>
                    {c.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {dataset.issues.map((issue) => (
        <div
          key={issue.field}
          className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning-soft/50 px-3 py-2 text-[13px] text-foreground"
        >
          <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <span>
            <strong>{issue.field}</strong>: {issue.message}{" "}
            <button className="font-medium text-primary hover:underline">Apply one-click fix</button>
          </span>
        </div>
      ))}

      {/* Target column selector */}
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label htmlFor="target-col" className="text-sm font-medium text-foreground">
          Target column
        </label>
        <div className="relative sm:w-56">
          <select
            id="target-col"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="h-9 w-full appearance-none rounded-lg border border-border bg-surface px-3 pr-9 text-sm font-medium text-foreground"
          >
            {dataset.columns.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
        <Button size="lg">
          <Play className="h-4 w-4" aria-hidden="true" />
          Start AutoGluon Training
        </Button>
        <Button variant="outline" size="lg">Refine dataset</Button>
      </div>
    </AgentCard>
  )
}

function Mini({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted/60 px-3 py-2">
      <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
      <div className={cn("mt-0.5 text-base font-semibold tabular-nums", tone === "success" ? "text-success" : "text-foreground")}>
        {value}
      </div>
    </div>
  )
}
