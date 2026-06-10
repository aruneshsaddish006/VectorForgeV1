"use client"

import * as React from "react"
import { TrendingUp, ExternalLink, BarChart2, Zap, Globe } from "lucide-react"
import { AgentCard, MetricBlock } from "./agent-card"
import { Expandable } from "@/components/ui/expandable"
import { cn } from "@/lib/utils"

type RevenueStat = {
  label: string
  value: string
  description: string
  tone?: "default" | "warning" | "success" | "primary"
}

type IndustryAdoption = {
  adoption_pct: number
  headline: string
  year: string
}

type AiWorkflowStat = {
  metric: string
  value: string
  description: string
}

type ChartBar = {
  label: string
  before: number
  after: number
  unit: string
}

type ExaSource = {
  title: string
  url: string
  snippet: string
}

export type DiscoveryCardData = {
  business_problem?: string
  domain?: string
  revenue_impact_headline?: string
  revenue_stats?: RevenueStat[]
  industry_adoption?: IndustryAdoption | null
  ai_workflow_stats?: AiWorkflowStat[]
  trend_insights?: string[]
  chart_data?: ChartBar[]
  exa_sources?: ExaSource[]
}

export function DiscoveryCard({ cardData }: { cardData: DiscoveryCardData }) {
  const {
    domain = "",
    revenue_impact_headline = "",
    revenue_stats = [],
    industry_adoption,
    ai_workflow_stats = [],
    trend_insights = [],
    chart_data = [],
    exa_sources = [],
  } = cardData

  return (
    <AgentCard
      title="Industry Discovery"
      status="complete"
      icon={TrendingUp}
      source={`${domain ? domain.charAt(0).toUpperCase() + domain.slice(1) + " · " : ""}Sourced via Exa Search`}
    >
      {revenue_impact_headline && (
        <p className="text-sm leading-relaxed text-muted-foreground">
          {revenue_impact_headline}
        </p>
      )}

      {/* Revenue impact stats */}
      {revenue_stats.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {revenue_stats.map((stat, i) => (
            <MetricBlock
              key={i}
              label={stat.label}
              value={stat.value}
              hint={stat.description}
              tone={stat.tone ?? "default"}
            />
          ))}
        </div>
      )}

      {/* Industry AI adoption bar */}
      {industry_adoption && (
        <div className="mt-4 rounded-lg border border-border bg-surface-muted/60 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-primary" aria-hidden="true" />
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Industry AI Adoption · {industry_adoption.year}
              </span>
            </div>
            <span className="text-sm font-bold text-primary">{industry_adoption.adoption_pct}%</span>
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">{industry_adoption.headline}</p>
          <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-primary transition-all duration-700"
              style={{ width: `${Math.min(100, Math.max(0, industry_adoption.adoption_pct))}%` }}
              role="progressbar"
              aria-valuenow={industry_adoption.adoption_pct}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>
      )}

      {/* Before / After AI chart */}
      {chart_data.length > 0 && (
        <div className="mt-4 rounded-lg border border-border bg-surface-muted/40 p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-primary" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Impact of AI Workflow
            </span>
          </div>

          <div className="space-y-3.5">
            {chart_data.map((bar, i) => (
              <ChartRow key={i} bar={bar} />
            ))}
          </div>

          <div className="mt-3 flex items-center gap-4 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-3 rounded-sm bg-muted-foreground/40" />
              Before AI
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-3 rounded-sm bg-primary" />
              With AI
            </span>
          </div>
        </div>
      )}

      {/* AI workflow optimisation stats */}
      {ai_workflow_stats.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-2">
            <Zap className="h-4 w-4 text-success" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              AI Workflow Optimisation
            </span>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-3">
            {ai_workflow_stats.map((stat, i) => (
              <MetricBlock
                key={i}
                label={stat.metric}
                value={stat.value}
                hint={stat.description}
                tone="success"
              />
            ))}
          </div>
        </div>
      )}

      {/* Trend insights */}
      {trend_insights.length > 0 && (
        <ul className="mt-4 space-y-2">
          {trend_insights.map((insight, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted-foreground">
              <span className="mt-1 shrink-0 text-primary">→</span>
              <span className="leading-relaxed">{insight}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Exa sources */}
      {exa_sources.length > 0 && (
        <Expandable label="Sources" className="mt-3">
          <ul className="space-y-3">
            {exa_sources.map((src, i) => (
              <li key={i} className="text-[13px] text-muted-foreground">
                {src.snippet && <p className="leading-relaxed">{src.snippet}</p>}
                {src.url && (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                  >
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    {src.title || src.url}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </Expandable>
      )}
    </AgentCard>
  )
}

function ChartRow({ bar }: { bar: ChartBar }) {
  const beforePct = Math.min(100, Math.max(0, bar.before))
  const afterPct = Math.min(100, Math.max(0, bar.after))
  const improvement = beforePct > 0 ? Math.round(((beforePct - afterPct) / beforePct) * 100) : 0

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[12px]">
        <span className="font-medium text-foreground">{bar.label}</span>
        <span className={cn("text-[11px] font-semibold", improvement > 0 ? "text-success" : "text-muted-foreground")}>
          {improvement > 0 ? `−${improvement}% ${bar.unit}` : bar.unit}
        </span>
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-right text-[10px] text-muted-foreground">Before</span>
          <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-muted-foreground/40 transition-all duration-500"
              style={{ width: `${beforePct}%` }}
            />
          </div>
          <span className="w-8 text-right text-[10px] font-medium text-muted-foreground">{beforePct}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-right text-[10px] text-muted-foreground">With AI</span>
          <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-primary transition-all duration-700"
              style={{ width: `${afterPct}%` }}
            />
          </div>
          <span className="w-8 text-right text-[10px] font-medium text-primary">{afterPct}</span>
        </div>
      </div>
    </div>
  )
}
