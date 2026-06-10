"use client"

import * as React from "react"
import { ArrowUp, Paperclip, Sparkles, X, FileText, Table2, File } from "lucide-react"
import { Button } from "@/components/ui/button"

const SUGGESTIONS = [
  "Build a churn dataset from the web",
  "Enrich my customer CSV",
  "Optimize a support RAG pipeline",
]

type Props = {
  onSubmit?: (text: string) => void
  onFileSelect?: (file: File) => void
  disabled?: boolean
  placeholder?: string
  acceptedFormats?: string
}

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase()
  if (ext === "pdf") return FileText
  if (ext === "csv" || ext === "parquet") return Table2
  return File
}

export function Composer({
  onSubmit,
  onFileSelect,
  disabled = false,
  placeholder = "Describe a business problem, or ask the agent to source data…",
  acceptedFormats = ".csv,.parquet,.pdf",
}: Props) {
  const [value, setValue] = React.useState("")
  const [pendingFile, setPendingFile] = React.useState<File | null>(null)
  const fileRef = React.useRef<HTMLInputElement>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  function submitMessage() {
    const text = value.trim()
    if (!text || disabled) return
    onSubmit?.(text)
    setValue("")
    setPendingFile(null)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submitMessage()
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      setPendingFile(file)
      onFileSelect?.(file)
      e.target.value = ""
    }
  }

  const FileIcon = pendingFile ? fileIcon(pendingFile.name) : null

  return (
    <div className="shrink-0 border-t border-border bg-surface-panel px-4 py-3 backdrop-blur-xl sm:px-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-2 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              disabled={disabled}
              onClick={() => setValue(s)}
              className="app-control flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold text-muted-foreground hover:border-primary/40 hover:text-foreground"
            >
              <Sparkles className="h-3 w-3 text-primary" aria-hidden="true" />
              {s}
            </button>
          ))}
        </div>

        {pendingFile && FileIcon && (
          <div className="mb-2 flex flex-wrap gap-2">
            <span className="flex items-center gap-1.5 rounded-full border border-border bg-surface-muted pl-2 pr-1 py-1 text-xs font-medium text-foreground">
              <FileIcon className="h-3.5 w-3.5 text-primary shrink-0" aria-hidden="true" />
              <span className="max-w-[200px] truncate">{pendingFile.name}</span>
              <button
                type="button"
                onClick={() => setPendingFile(null)}
                className="ml-0.5 rounded-full p-0.5 text-muted-foreground hover:text-foreground"
                aria-label="Remove attachment"
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </span>
          </div>
        )}

        <form
          onSubmit={(e) => { e.preventDefault(); submitMessage() }}
          className="app-panel-raised flex items-end gap-2 rounded-[22px] p-2 focus-within:border-primary/50"
        >
          <input
            ref={fileRef}
            type="file"
            accept={acceptedFormats}
            className="sr-only"
            onChange={handleFileChange}
            aria-hidden="true"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Attach dataset file"
            className="shrink-0"
            disabled={disabled}
            onClick={() => fileRef.current?.click()}
          >
            <Paperclip className="h-5 w-5" aria-hidden="true" />
          </Button>
          <label htmlFor="composer" className="sr-only">
            Message the AI strategy agent
          </label>
          <textarea
            ref={textareaRef}
            id="composer"
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            className="max-h-52 min-h-[2.25rem] flex-1 resize-none overflow-y-auto bg-transparent py-1.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
          />
          <Button
            type="submit"
            size="icon"
            aria-label="Send message"
            className="shrink-0"
            disabled={!value.trim() || disabled}
          >
            <ArrowUp className="h-5 w-5" aria-hidden="true" />
          </Button>
        </form>
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          Agents act with human-in-the-loop approval for any paid or irreversible step.
        </p>
      </div>
    </div>
  )
}
