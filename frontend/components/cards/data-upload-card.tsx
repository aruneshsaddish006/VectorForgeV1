"use client"

import * as React from "react"
import { Upload, Search, SkipForward, FileText, Table2, CheckCircle2, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DataUploadCard({
  problemId,
  problemName,
  engine,
  acceptedFormats,
  onUploadFile,
  onDiscover,
  onSkip,
  loading = false,
}: {
  problemId: string
  problemName: string
  engine: "autogluon" | "autorag"
  acceptedFormats?: string
  onUploadFile?: (file: File) => void
  onDiscover?: () => void
  onSkip?: () => void
  loading?: boolean
}) {
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null)
  const isRag = engine === "autorag"

  const acceptType = acceptedFormats ?? (isRag ? ".pdf,.csv" : ".csv,.parquet")
  const fileLabel = isRag ? "PDF or CSV corpus" : "CSV or Parquet dataset"
  const FileIcon = isRag ? FileText : Table2

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      onUploadFile?.(file)
    }
    e.target.value = ""
  }

  return (
    <div className="w-full overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      <header className="border-b border-border px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2.5">
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
              isRag ? "bg-warning-soft text-warning" : "bg-info-soft text-primary",
            )}
          >
            <FileIcon className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold text-foreground">{problemName}</h3>
            <p className="text-[11px] text-muted-foreground">
              {isRag
                ? "RAG · GenAI — upload document corpus"
                : "Predictive · AutoGluon — upload training data"}
            </p>
          </div>
        </div>
      </header>

      <div className="px-4 py-4 sm:px-5">
        {selectedFile ? (
          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-muted px-4 py-4">
            <span
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                isRag ? "bg-warning-soft text-warning" : "bg-info-soft text-primary",
              )}
            >
              <FileIcon className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-foreground">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">{formatFileSize(selectedFile.size)}</p>
            </div>
            <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" aria-label="File selected" />
          </div>
        ) : (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            className={cn(
              "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed py-8 transition-colors",
              "border-border hover:border-primary/50 hover:bg-surface-muted/50",
              loading && "cursor-not-allowed opacity-50",
            )}
            aria-label={`Upload ${fileLabel} for ${problemName}`}
          >
            <Upload className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium text-foreground">Upload {fileLabel}</p>
            <p className="text-xs text-muted-foreground">
              {isRag ? "PDF · CSV" : "CSV · Parquet"} — click or drag &amp; drop
            </p>
          </button>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept={acceptType}
          className="sr-only"
          onChange={handleFileChange}
          aria-hidden="true"
          tabIndex={-1}
          data-prob-id={problemId}
        />

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {selectedFile ? (
            <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={loading}>
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Replace file
            </Button>
          ) : (
            <Button onClick={() => fileInputRef.current?.click()} disabled={loading}>
              <Upload className="h-4 w-4" aria-hidden="true" />
              Upload file
            </Button>
          )}
          <Button variant="outline" onClick={onDiscover} disabled={loading}>
            <Search className="h-4 w-4" aria-hidden="true" />
            Discover dataset
          </Button>
          <Button
            variant="ghost"
            onClick={onSkip}
            disabled={loading}
            className="text-muted-foreground hover:text-foreground"
          >
            <SkipForward className="h-4 w-4" aria-hidden="true" />
            Skip for now
          </Button>
        </div>
      </div>
    </div>
  )
}
