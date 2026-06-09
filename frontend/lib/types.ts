import type { LucideIcon } from "lucide-react"

export type AgentStatus =
  | "draft"
  | "waiting-approval"
  | "running"
  | "complete"
  | "needs-attention"
  | "failed"
  | "deployed"

export type AgentName =
  | "Intent Agent"
  | "Strategy Agent"
  | "Data Agent"
  | "Training Agent"
  | "RAG Agent"
  | "Deployment Agent"
  | "Billing Agent"

export type NavSection = {
  id: string
  label: string
  icon: LucideIcon
  badge?: string | number
}

export type EffortLevel = "low" | "medium" | "high" | "xhigh"

export type EffortOption = {
  value: EffortLevel
  label: string
  cost: string
  description: string
}

export type SchemaColumn = {
  name: string
  type: "string" | "number" | "integer" | "boolean"
  nullPct: number
  sample: string
  source: "uploaded" | "exa" | "enriched"
}

export type ActivityEntry = {
  id: string
  agent: AgentName
  message: string
  time: string
  status: AgentStatus
  tool?: string
  cost?: string
  detail?: string
}

export type LeaderboardRow = {
  rank: number
  model: string
  metric: number
  inferTime: string
  best?: boolean
}

export type DataSourcePath = {
  id: "upload" | "exa" | "hybrid"
  title: string
  bestFor: string
  input: string
  time: string
  cost: string
  output: string
}

export type StrategyUseCase = {
  name: string
  type: string
  confidence: string
  roi: string
}

export type StrategyMetric = {
  label: string
  value: string
  hint?: string
  tone?: "default" | "success" | "warning" | "primary"
}

export type StrategySummary = {
  summary: string
  metrics: StrategyMetric[]
  useCases: StrategyUseCase[]
}

export type ExaPreviewRow = {
  company: string
  arr: string
  emp: number
  nps: number
  tickets: number
  churned: boolean
}

export type ExaProvenance = {
  field: string
  src: string
}

export type ExaRun = {
  id: string
  datasetId: string
  query: string
  efforts: EffortOption[]
  selectedEffort: EffortLevel
  status: "waiting-approval" | "running" | "complete"
  stages: string[]
  activeStage: number
  stats: {
    rows: string
    features: string
    qualityScore: string
    runCost: string
  }
  previewRows: ExaPreviewRow[]
  provenance: ExaProvenance[]
}

export type DatasetIssue = {
  field: string
  message: string
}

export type DatasetSchema = {
  id: string
  name: string
  rowCount: number
  columnCount: number
  taskType: string
  qualityScore: number
  targetColumn: string
  columns: SchemaColumn[]
  issues: DatasetIssue[]
}

export type TrainingRun = {
  id: string
  status: AgentStatus
  metrics: {
    bestRocAuc: string
    modelsTrained: string
    trainTime: string
    computeCost: string
  }
  leaderboard: LeaderboardRow[]
  featureImportance: { f: string; w: number }[]
}

export type RagRun = {
  id: string
  status: AgentStatus
  metrics: {
    faithfulness: string
    contextRecall: string
    trialsRun: string
    p95Latency: string
  }
  pipeline: { stage: string; detail: string; value: string }[]
  bestConfig: { k: string; v: string }[]
}

// ---------------------------------------------------------------------------
// Conversational agent types
// ---------------------------------------------------------------------------

export type InterruptType =
  | "clarification"
  | "sub_problem_confirmation"
  | "dataset_source_choice"
  | "awaiting_upload"
  | "exa_results_review"
  | "dataset_cost_approval"
  | "schema_confirmation"
  | "final_review"

export type ConversationMessage = {
  role: "user" | "agent"
  agentName?: string | null
  content: string
  timestamp: string
  cardType?: string | null
  cardData?: Record<string, unknown> | null
}

export type InterruptOption = { value: string; label: string }

export type InterruptPayload = {
  type: InterruptType
  message: string
  data?: Record<string, unknown> | null
  options?: InterruptOption[] | null
  estimatedCostUsd?: number | null
  questions?: string[] | null
  finalOutput?: Record<string, unknown> | null
  problemId?: string | null
  problemName?: string | null
  engine?: string | null
}

export type ConversationSession = {
  sessionId: string
  status: string
  messages: ConversationMessage[]
  interrupt: InterruptPayload | null
  finalOutput?: Record<string, unknown> | null
}

export type DemoWorkspace = {
  strategy: StrategySummary
  dataSources: DataSourcePath[]
  exaRun: ExaRun
  dataset: DatasetSchema
  training: TrainingRun
  rag: RagRun
  activity: ActivityEntry[]
}
