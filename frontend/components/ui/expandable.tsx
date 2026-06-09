"use client"

import * as React from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

export function Expandable({
  label,
  children,
  defaultOpen = false,
  className,
}: {
  label: string
  children: React.ReactNode
  defaultOpen?: boolean
  className?: string
}) {
  const [open, setOpen] = React.useState(defaultOpen)
  return (
    <div className={cn("border-t border-border", className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between py-2.5 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        {label}
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", open && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      {open && <div className="pb-3">{children}</div>}
    </div>
  )
}
