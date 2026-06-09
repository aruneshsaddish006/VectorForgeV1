import { CloudCog, Copy, ExternalLink, Globe2, Boxes } from "lucide-react"
import { AgentCard } from "./agent-card"
import { Button } from "@/components/ui/button"

const ENDPOINTS = [
  { icon: Boxes, label: "Model API", url: "https://api.forgeai.app/v1/churn-predict", method: "POST" },
  { icon: Globe2, label: "RAG Web Interface", url: "https://churn-copilot.vercel.app", method: "GET" },
]

export function DeploymentCard() {
  return (
    <AgentCard
      title="Deployment Ready"
      status="deployed"
      icon={CloudCog}
      source="Deployment Agent · AWS endpoint + Vercel frontend"
    >
      <p className="text-sm leading-relaxed text-foreground">
        Your churn prediction model and support RAG interface are live. Endpoints are secured with
        per-workspace API keys.
      </p>

      <div className="mt-4 space-y-2.5">
        {ENDPOINTS.map((e) => {
          const Icon = e.icon
          return (
            <div
              key={e.label}
              className="flex flex-col gap-2 rounded-lg border border-border bg-surface-muted/50 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-foreground">{e.label}</div>
                  <div className="truncate font-mono text-[11px] text-muted-foreground">
                    <span className="mr-1.5 rounded bg-surface px-1 py-0.5 font-sans font-medium text-primary">
                      {e.method}
                    </span>
                    {e.url}
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <Button variant="outline" size="sm" aria-label={`Copy ${e.label} URL`}>
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                  Copy
                </Button>
                <Button variant="secondary" size="sm">
                  Open
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button>View deployment dashboard</Button>
        <Button variant="outline">Manage API keys</Button>
      </div>
    </AgentCard>
  )
}
