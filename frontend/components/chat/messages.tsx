import * as React from "react"
import { ForgeAiIcon } from "@/components/brand/forge-ai-icon"
import { cn } from "@/lib/utils"

export function UserMessage({ children, time }: { children: React.ReactNode; time?: string }) {
  return (
    <div className="flex justify-end">
      <div className="flex max-w-[78%] flex-col items-end gap-1">
        <div className="app-accent-shadow rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
          {children}
        </div>
        {time && <span className="px-1 text-[11px] text-muted-foreground">{time}</span>}
      </div>
    </div>
  )
}

export function AgentMessage({
  children,
  agent = "Strategy Agent",
  time,
}: {
  children: React.ReactNode
  agent?: string
  time?: string
}) {
  return (
    <div className="flex gap-3">
      <ForgeAiIcon size="sm" className="mt-0.5 rounded-lg" />
      <div className="flex min-w-0 max-w-[88%] flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-foreground">{agent}</span>
          {time && <span className="text-[11px] text-muted-foreground">{time}</span>}
        </div>
        <div className="app-panel-raised rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm leading-relaxed text-foreground">
          {children}
        </div>
      </div>
    </div>
  )
}

/** Full-width slot for embedded job/system cards */
export function SystemCardSlot({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("pl-0 sm:pl-11", className)}>{children}</div>
}
