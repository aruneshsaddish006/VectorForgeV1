"use client"

import { CheckCircle2, ArrowRight, Table2, FileText, Copy } from "lucide-react"
import { cn } from "@/lib/utils"
import { AgentCard } from "./agent-card"
import { Button } from "@/components/ui/button"

type ColumnMeta = {
  inferred_name?: string
  type?: string
  confidence?: "high" | "medium" | "low"
}

const CONFIDENCE_STYLE: Record<string, string> = {
  high: "bg-success-soft text-success",
  medium: "bg-warning-soft text-warning",
  low: "bg-error-soft text-destructive",
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => undefined)
}

export function DataPreviewCard({
  problemName,
  engine,
  s3Path,
  datasetDescription,
  inferredColumns,
  onConfirm,
  onAdjust,
  loading = false,
}: {
  problemName: string
  engine?: string | null
  s3Path?: string | null
  datasetDescription?: string | null
  inferredColumns?: Record<string, ColumnMeta> | null
  onConfirm?: () => void
  onAdjust?: () => void
  loading?: boolean
}) {
  const isRag = engine === "autorag"
  const Icon = isRag ? FileText : Table2
  const columnEntries = inferredColumns ? Object.entries(inferredColumns) : []

  return (
    <AgentCard
      title={`Dataset ready — ${problemName}`}
      status="waiting-approval"
      icon={Icon}
      source={`Data Agent · ${isRag ? "AutoRAG" : "AutoGluon"} · confirm before training`}
    >
      {datasetDescription && (
        <p className="text-sm leading-relaxed text-muted-foreground">{datasetDescription}</p>
      )}

      {s3Path && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-surface-muted px-3 py-2">
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground">{s3Path}</span>
          <button
            type="button"
            onClick={() => copyToClipboard(s3Path)}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            title="Copy S3 path"
          >
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      )}

      {columnEntries.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-muted text-[11px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">Column name</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="hidden px-3 py-2 font-medium sm:table-cell">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {columnEntries.map(([role, meta]) => (
                <tr key={role} className="hover:bg-surface-muted/50">
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{role}</td>
                  <td className="px-3 py-2 font-medium text-foreground">{meta.inferred_name ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-xs text-primary">{meta.type ?? "—"}</td>
                  <td className="hidden px-3 py-2 sm:table-cell">
                    {meta.confidence && (
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-[11px] font-medium capitalize",
                          CONFIDENCE_STYLE[meta.confidence] ?? "",
                        )}
                      >
                        {meta.confidence}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
        <Button onClick={onConfirm} disabled={loading}>
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          Confirm and continue
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
        <Button variant="outline" onClick={onAdjust} disabled={loading}>
          Adjust column names
        </Button>
      </div>
    </AgentCard>
  )
}
