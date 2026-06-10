"use client"

import * as React from "react"
import { CheckCircle2, ArrowRight, Table2, FileText, Copy, AlertTriangle } from "lucide-react"
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

/** Case-insensitive best-match of an inferred name against actual CSV columns. */
function findBestMatch(inferred: string, actual: string[]): string {
  if (!actual.length) return inferred
  const lower = inferred.toLowerCase()
  return (
    actual.find((c) => c.toLowerCase() === lower) ??
    actual.find((c) => c.toLowerCase().includes(lower) || lower.includes(c.toLowerCase())) ??
    actual[0]
  )
}

export function DataPreviewCard({
  problemName,
  engine,
  s3Path,
  datasetDescription,
  inferredColumns,
  actualColumns,
  onConfirm,
  onAdjust,
  loading = false,
}: {
  problemName: string
  engine?: string | null
  s3Path?: string | null
  datasetDescription?: string | null
  inferredColumns?: Record<string, ColumnMeta> | null
  actualColumns?: string[] | null
  onConfirm?: (columnOverrides: Record<string, string>) => void
  onAdjust?: () => void
  loading?: boolean
}) {
  const isRag = engine === "autorag"
  const Icon = isRag ? FileText : Table2
  const columnEntries = inferredColumns ? Object.entries(inferredColumns) : []
  const hasActualColumns = Boolean(actualColumns && actualColumns.length > 0)

  // Initialise selections: best-match each inferred column against actual CSV columns
  const [selections, setSelections] = React.useState<Record<string, string>>(() => {
    if (!hasActualColumns || !inferredColumns) return {}
    return Object.fromEntries(
      Object.entries(inferredColumns).map(([role, meta]) => [
        role,
        findBestMatch(meta.inferred_name ?? "", actualColumns!),
      ]),
    )
  })

  function handleSelect(role: string, value: string) {
    setSelections((prev) => ({ ...prev, [role]: value }))
  }

  function handleConfirm() {
    if (!onConfirm) return
    // Always pass selections so the backend uses the user-confirmed actual column
    // names rather than the LLM-inferred ones.
    onConfirm(hasActualColumns ? selections : {})
  }

  // Warn when the LLM-inferred name doesn't exist verbatim in actual columns
  function isMismatch(meta: ColumnMeta): boolean {
    if (!hasActualColumns) return false
    const inferred = meta.inferred_name ?? ""
    return !actualColumns!.some((c) => c.toLowerCase() === inferred.toLowerCase())
  }

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
          <div className="border-b border-border bg-surface-muted px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Column mapping
            </p>
            {hasActualColumns && (
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                Select the correct column from your CSV for each role. AI suggestion is pre-filled.
              </p>
            )}
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-muted/60 text-[11px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">
                  {hasActualColumns ? "Confirm column" : "AI-inferred name"}
                </th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="hidden px-3 py-2 font-medium sm:table-cell">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {columnEntries.map(([role, meta]) => {
                const mismatch = isMismatch(meta)
                return (
                  <tr key={role} className="hover:bg-surface-muted/50">
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{role}</td>
                    <td className="px-3 py-2">
                      {hasActualColumns ? (
                        <div className="flex flex-col gap-1">
                          <select
                            value={selections[role] ?? ""}
                            onChange={(e) => handleSelect(role, e.target.value)}
                            disabled={loading}
                            className="w-full rounded border border-border bg-surface px-2 py-1 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                          >
                            {actualColumns!.map((col) => (
                              <option key={col} value={col}>{col}</option>
                            ))}
                          </select>
                          {mismatch && (
                            <span className="flex items-center gap-1 text-[10px] text-warning">
                              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                              AI suggested &ldquo;{meta.inferred_name}&rdquo; — not in CSV
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="font-medium text-foreground">{meta.inferred_name ?? "—"}</span>
                      )}
                    </td>
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
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {hasActualColumns && (
        <details className="mt-3">
          <summary className="cursor-pointer text-[11px] text-muted-foreground hover:text-foreground">
            All CSV columns ({actualColumns!.length})
          </summary>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {actualColumns!.map((col) => (
              <span
                key={col}
                className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-foreground"
              >
                {col}
              </span>
            ))}
          </div>
        </details>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
        <Button onClick={handleConfirm} disabled={loading}>
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          Confirm and continue
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
        <Button variant="outline" onClick={onAdjust} disabled={loading}>
          Adjust
        </Button>
      </div>
    </AgentCard>
  )
}
