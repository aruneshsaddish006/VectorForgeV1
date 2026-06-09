"use client"

import * as React from "react"
import { ArrowUp, Paperclip, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"

const SUGGESTIONS = [
  "Build a churn dataset from the web",
  "Enrich my customer CSV",
  "Optimize a support RAG pipeline",
]

export function Composer() {
  const [value, setValue] = React.useState("")
  return (
    <div className="border-t border-border bg-surface px-4 py-3 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-2 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setValue(s)}
              className="flex items-center gap-1.5 rounded-full border border-border bg-surface-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground hover:border-primary/40 hover:text-foreground"
            >
              <Sparkles className="h-3 w-3 text-primary" aria-hidden="true" />
              {s}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => e.preventDefault()}
          className="flex items-end gap-2 rounded-xl border border-border bg-surface p-2 shadow-sm focus-within:border-primary/50"
        >
          <Button type="button" variant="ghost" size="icon" aria-label="Attach file" className="shrink-0">
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
            placeholder="Describe a business problem, or ask the agent to source data…"
            className="max-h-32 min-h-[2.25rem] flex-1 resize-none bg-transparent py-1.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          <Button type="submit" size="icon" aria-label="Send message" className="shrink-0" disabled={!value.trim()}>
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
