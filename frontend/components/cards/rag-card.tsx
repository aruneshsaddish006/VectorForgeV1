import { Network, ArrowRight } from "lucide-react"
import { AgentCard, MetricBlock } from "./agent-card"
import { Button } from "@/components/ui/button"
import { Expandable } from "@/components/ui/expandable"
import type { RagRun } from "@/lib/types"

const PIPELINE = [
  { stage: "Parse", detail: "PDF + web corpus", value: "1,204 docs" },
  { stage: "Chunk", detail: "Semantic, 512 tokens", value: "8,930 chunks" },
  { stage: "QA Gen", detail: "Synthetic eval set", value: "320 pairs" },
  { stage: "Optimize", detail: "Trial sweep", value: "24 configs" },
]

const BEST_CONFIG = [
  { k: "Retriever", v: "hybrid (BM25 + dense)" },
  { k: "Embedding", v: "text-embedding-3-large" },
  { k: "Reranker", v: "cohere-rerank-v3" },
  { k: "Top-k", v: "6" },
  { k: "Chunk size", v: "512 / 64 overlap" },
]

const DEFAULT_RAG: RagRun = {
  id: "rag_demo",
  status: "complete",
  metrics: { faithfulness: "0.94", contextRecall: "0.89", trialsRun: "24", p95Latency: "640ms" },
  pipeline: PIPELINE,
  bestConfig: BEST_CONFIG,
}

export function RagCard({ rag = DEFAULT_RAG }: { rag?: RagRun }) {
  return (
    <AgentCard
      title="AutoRAG Best Pipeline Selected"
      status="complete"
      icon={Network}
      source="RAG Agent · 24 trials on AWS EC2 + pgvector"
    >
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <MetricBlock label="Faithfulness" value={rag.metrics.faithfulness} tone="success" />
        <MetricBlock label="Context recall" value={rag.metrics.contextRecall} tone="success" />
        <MetricBlock label="Trials run" value={rag.metrics.trialsRun} />
        <MetricBlock label="P95 latency" value={rag.metrics.p95Latency} />
      </div>

      {/* Pipeline stages */}
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {rag.pipeline.map((s, i) => (
          <div key={s.stage} className="relative rounded-lg border border-border bg-surface-muted/50 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">{s.stage}</div>
            <div className="mt-1 text-sm font-semibold text-foreground">{s.value}</div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">{s.detail}</div>
            {i < rag.pipeline.length - 1 && (
              <ArrowRight
                className="absolute -right-2.5 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-muted-foreground sm:block"
                aria-hidden="true"
              />
            )}
          </div>
        ))}
      </div>

      <Expandable label="Winning configuration" className="mt-4" defaultOpen>
        <dl className="grid grid-cols-1 gap-1.5 rounded-lg bg-surface-muted/60 p-3 sm:grid-cols-2">
          {rag.bestConfig.map((c) => (
            <div key={c.k} className="flex items-center justify-between gap-2 text-[13px]">
              <dt className="text-muted-foreground">{c.k}</dt>
              <dd className="font-mono font-medium text-foreground">{c.v}</dd>
            </div>
          ))}
        </dl>
      </Expandable>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button>
          Deploy RAG endpoint
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
        <Button variant="outline">Test in playground</Button>
      </div>
    </AgentCard>
  )
}
