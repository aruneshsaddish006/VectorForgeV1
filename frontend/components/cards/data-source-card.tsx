"use client"

import * as React from "react"
import { Upload, Globe, Combine, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import type { DataSourcePath } from "@/lib/types"

type PathId = "upload" | "exa" | "hybrid"

const PATHS: DataSourcePath[] = [
  {
    id: "upload",
    title: "Upload my data",
    bestFor: "You already have labelled data",
    input: "CSV · Excel · PDF · DB connection",
    time: "~30 sec validation",
    cost: "No credits used",
    output: "Validated typed schema",
  },
  {
    id: "exa",
    title: "Build dataset from web",
    bestFor: "You have no training data",
    input: "Natural language query",
    time: "1–6 min build",
    cost: "From $0.025 / run",
    output: "Schema-validated JSON",
  },
  {
    id: "hybrid",
    title: "Enrich my data",
    bestFor: "You have rows, need more columns",
    input: "Seed CSV + web enrichment",
    time: "2–8 min build",
    cost: "From $0.10 / run",
    output: "Merged enriched dataset",
  },
]

const ICON_MAP: Record<PathId, React.ElementType> = {
  upload: Upload,
  exa: Globe,
  hybrid: Combine,
}

export function DataSourceCard({
  paths = PATHS,
  problemName,
  acceptedFormats,
  onSelect,
  onUploadFile,
  loading = false,
}: {
  paths?: DataSourcePath[]
  problemName?: string
  acceptedFormats?: string
  onSelect?: (choice: "upload" | "discover" | "skip") => void
  onUploadFile?: (file: File) => void
  loading?: boolean
}) {
  const [selected, setSelected] = React.useState<PathId>("upload")
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const acceptType = acceptedFormats ?? ".csv,.parquet,.pdf"
  const selectedPath = paths.find((p) => p.id === selected)

  function handleContinue() {
    if (loading) return
    if (selected === "upload") {
      if (onUploadFile) {
        fileInputRef.current?.click()
      } else {
        onSelect?.("upload")
      }
      return
    }
    onSelect?.(selected === "hybrid" ? "skip" : "discover")
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onUploadFile?.(file)
    e.target.value = ""
  }

  return (
    <div className="w-full overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      <header className="border-b border-border px-4 py-3 sm:px-5">
        <h3 className="text-[15px] font-semibold text-foreground">
          {problemName ? `Source data for: ${problemName}` : "Choose how to source training data"}
        </h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Data Agent will validate, store in your S3 bucket, and confirm the schema before any training.
        </p>
      </header>

      <div className="px-4 py-4 sm:px-5">
        <div role="radiogroup" aria-label="Data source path" className="grid gap-3 md:grid-cols-3">
          {paths.map((p) => {
            const Icon = ICON_MAP[p.id as PathId] ?? Upload
            const active = selected === p.id
            return (
              <button
                key={p.id}
                role="radio"
                aria-checked={active}
                disabled={loading}
                onClick={() => setSelected(p.id as PathId)}
                className={cn(
                  "relative flex flex-col rounded-xl border p-4 text-left transition-all",
                  active
                    ? "border-primary bg-info-soft/40 ring-1 ring-primary"
                    : "border-border bg-surface hover:border-primary/40 hover:bg-surface-muted/50",
                  loading && "pointer-events-none opacity-50",
                )}
              >
                {active && (
                  <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Check className="h-3 w-3" aria-hidden="true" />
                  </span>
                )}
                <span
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-lg",
                    active ? "bg-primary text-primary-foreground" : "bg-surface-muted text-primary",
                  )}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <h4 className="mt-3 text-sm font-semibold text-foreground">{p.title}</h4>
                <dl className="mt-2.5 space-y-1.5 text-[12px]">
                  <Row label="Best for" value={p.bestFor} />
                  <Row label="Input" value={p.input} />
                  <Row label="Time" value={p.time} />
                  <Row label="Cost" value={p.cost} />
                  <Row label="Output" value={p.output} />
                </dl>
              </button>
            )
          })}
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Button onClick={handleContinue} disabled={loading}>
            Continue with {selectedPath?.title ?? "selection"}
          </Button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept={acceptType}
          className="sr-only"
          onChange={handleFileChange}
          aria-hidden="true"
          tabIndex={-1}
        />
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-foreground">{value}</dd>
    </div>
  )
}
