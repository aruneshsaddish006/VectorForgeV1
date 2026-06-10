"use client"

import * as React from "react"
import { ArrowUp, Paperclip, Sparkles } from "lucide-react"
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
}

export function Composer({
  onSubmit,
  onFileSelect,
  disabled = false,
  placeholder = "Describe a business problem, or ask the agent to source data…",
}: Props) {
  const [value, setValue] = React.useState("")
  const fileRef = React.useRef<HTMLInputElement>(null)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = value.trim()
    if (!text || disabled) return
    onSubmit?.(text)
    setValue("")
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as React.FormEvent)
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      onFileSelect?.(file)
      e.target.value = ""
    }
  }

  return (
    <div className="border-t border-border bg-surface-panel px-4 py-3 backdrop-blur-xl sm:px-6">
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

        <form
          onSubmit={handleSubmit}
          className="app-panel-raised flex items-end gap-2 rounded-[22px] p-2 focus-within:border-primary/50"
        >
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.parquet,.json"
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
            id="composer"
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            className="max-h-32 min-h-[2.25rem] flex-1 resize-none bg-transparent py-1.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
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
