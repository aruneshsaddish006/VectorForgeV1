import { Cpu, Trophy, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { AgentCard, MetricBlock } from "./agent-card"
import { Button } from "@/components/ui/button"
import { Expandable } from "@/components/ui/expandable"
import type { LeaderboardRow, TrainingRun } from "@/lib/types"

const LEADERBOARD: LeaderboardRow[] = [
  { rank: 1, model: "WeightedEnsemble_L2", metric: 0.921, inferTime: "12ms", best: true },
  { rank: 2, model: "LightGBM_BAG_L1", metric: 0.908, inferTime: "4ms" },
  { rank: 3, model: "CatBoost_BAG_L1", metric: 0.903, inferTime: "6ms" },
  { rank: 4, model: "XGBoost_BAG_L1", metric: 0.897, inferTime: "5ms" },
  { rank: 5, model: "RandomForest_BAG_L1", metric: 0.882, inferTime: "9ms" },
]

const DEFAULT_TRAINING: TrainingRun = {
  id: "train_demo",
  status: "complete",
  metrics: { bestRocAuc: "0.921", modelsTrained: "11", trainTime: "6m 24s", computeCost: "$0.64" },
  leaderboard: LEADERBOARD,
  featureImportance: [
    { f: "nps_score", w: 0.34 },
    { f: "support_tickets", w: 0.27 },
    { f: "arr_usd", w: 0.19 },
    { f: "employee_count", w: 0.12 },
  ],
}

export function TrainingCard({ training = DEFAULT_TRAINING }: { training?: TrainingRun }) {
  return (
    <AgentCard
      title="AutoGluon Training Complete"
      status="complete"
      icon={Cpu}
      source="Training Agent · TabularPredictor on AWS SageMaker"
    >
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <MetricBlock label="Best ROC-AUC" value={training.metrics.bestRocAuc} tone="success" />
        <MetricBlock label="Models trained" value={training.metrics.modelsTrained} />
        <MetricBlock label="Train time" value={training.metrics.trainTime} />
        <MetricBlock label="Compute cost" value={training.metrics.computeCost} />
      </div>

      <div className="mt-4 overflow-hidden rounded-lg border border-border">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-surface-muted text-[11px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">Model</th>
              <th className="px-3 py-2 font-medium">ROC-AUC</th>
              <th className="hidden px-3 py-2 font-medium sm:table-cell">Infer</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {training.leaderboard.map((row) => (
              <tr key={row.model} className={cn("hover:bg-surface-muted/50", row.best && "bg-success-soft/40")}>
                <td className="px-3 py-2.5">
                  {row.best ? (
                    <Trophy className="h-4 w-4 text-success" aria-label="Best model" />
                  ) : (
                    <span className="text-muted-foreground">{row.rank}</span>
                  )}
                </td>
                <td className="px-3 py-2.5 font-mono font-medium text-foreground">{row.model}</td>
                <td className="px-3 py-2.5 font-mono tabular-nums text-foreground">{row.metric.toFixed(3)}</td>
                <td className="hidden px-3 py-2.5 font-mono text-muted-foreground sm:table-cell">{row.inferTime}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Expandable label="Feature importance & diagnostics" className="mt-4">
        <ul className="space-y-2">
          {training.featureImportance.map((item) => (
            <li key={item.f} className="flex items-center gap-3">
              <span className="w-32 shrink-0 font-mono text-xs text-foreground">{item.f}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${item.w * 100}%` }} />
              </div>
              <span className="w-10 shrink-0 text-right font-mono text-xs tabular-nums text-muted-foreground">
                {item.w.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </Expandable>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button>
          Deploy best model
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
        <Button variant="outline">Compare models</Button>
      </div>
    </AgentCard>
  )
}
