import Link from "next/link"
import {
  ArrowRight,
  BadgeDollarSign,
  CheckCircle2,
  ChevronRight,
  Cloud,
  DatabaseZap,
  GitBranch,
  Layers3,
  LockKeyhole,
  Radar,
  Rocket,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react"
import { ForgeAiIcon } from "@/components/brand/forge-ai-icon"

const METRICS = [
  { value: "1", label: "conversation to start" },
  { value: "7", label: "autonomous agents" },
  { value: "3", label: "human approval gates" },
  { value: "0", label: "static demos" },
]

const AGENTS = [
  { name: "Intent", detail: "Turns a plain-language goal into structured context." },
  { name: "Strategy", detail: "Maps use cases, ROI, feasibility, and build plan." },
  { name: "Data", detail: "Uses Exa to build or enrich training datasets." },
  { name: "Training", detail: "Trains and tunes the best model on AWS." },
  { name: "RAG", detail: "Optimizes retrieval for grounded answers." },
  { name: "Deploy", detail: "Ships live inference and retrieval endpoints." },
  { name: "Billing", detail: "Meters usage and manages Stripe subscriptions." },
]

const STACK = [
  {
    title: "Vercel",
    label: "Product and model access",
    text: "Frontend, AI Gateway, and sandboxed build workflows.",
    icon: Sparkles,
  },
  {
    title: "AWS",
    label: "Cloud infrastructure",
    text: "RDS, S3, compute, training, artifacts, and serving endpoints.",
    icon: Cloud,
  },
  {
    title: "Exa",
    label: "Web intelligence",
    text: "Search, deep research, and dataset generation for agents.",
    icon: Search,
  },
  {
    title: "Stripe",
    label: "Monetization",
    text: "Checkout, subscriptions, usage gating, and billing approvals.",
    icon: BadgeDollarSign,
  },
]

const GUARDRAILS = [
  {
    title: "Plan and KPI approval",
    text: "Review the strategy, use cases, and target business metrics before any expensive work begins.",
  },
  {
    title: "Schema and data approval",
    text: "Confirm the dataset schema, target column, provenance, and quality before training.",
  },
  {
    title: "Billing and deploy approval",
    text: "Authorize spend and production deployment before an endpoint goes live.",
  },
]

const RECOVERY = [
  "Retry transient API failures with backoff",
  "Re-plan when tools return empty or invalid outputs",
  "Checkpoint state so runs resume after refresh or pause",
  "Escalate low-confidence decisions to a human gate",
]

const PLANS = [
  { name: "Free", price: "$0", detail: "Try one use case end-to-end" },
  { name: "Pro", price: "$49/mo", detail: "3 use cases, 10 Exa datasets, 5 RAG trials", featured: true },
  { name: "Enterprise", price: "$299/mo", detail: "Unlimited workflows, custom models, SLA" },
]

export default function HomePage() {
  return (
    <main className="min-h-dvh bg-canvas text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/92 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5 rounded-xl" aria-label="Forge AI home">
            <ForgeAiIcon size="md" priority />
            <span className="font-heading text-lg font-bold">Forge AI</span>
          </Link>

          <nav className="hidden items-center gap-7 text-sm font-semibold text-muted-foreground lg:flex">
            <a href="#agents" className="hover:text-foreground">Agents</a>
            <a href="#stack" className="hover:text-foreground">Stack</a>
            <a href="#controls" className="hover:text-foreground">Controls</a>
            <a href="#pricing" className="hover:text-foreground">Pricing</a>
          </nav>

          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="hidden h-9 items-center justify-center rounded-full px-4 text-sm font-semibold text-muted-foreground hover:bg-surface-muted hover:text-foreground sm:inline-flex"
            >
              Log in
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex h-9 items-center justify-center gap-2 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary-dark"
            >
              Open product
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8 lg:py-16">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-bold text-muted-foreground">
            <Rocket className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            Autonomous AI build team for enterprise workflows
          </div>

          <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-[1.02] tracking-normal sm:text-5xl lg:text-6xl">
            Describe a business problem. Ship a trained AI service.
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Forge AI turns one plain-language goal into strategy, data, model training, retrieval, deployment, and billing through a coordinated team of agents.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/dashboard"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-primary px-5 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary-dark"
            >
              Launch workspace
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              href="/signup"
              className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-surface px-5 text-sm font-bold text-foreground hover:bg-surface-muted"
            >
              Create account
            </Link>
          </div>

          <dl className="mt-9 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {METRICS.map((item) => (
              <div key={item.label} className="rounded-2xl border border-border bg-surface px-4 py-3">
                <dt className="text-xs font-semibold leading-5 text-muted-foreground">{item.label}</dt>
                <dd className="mt-1 text-3xl font-bold text-foreground">{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <ProductPreview />
      </section>

      <section className="border-y border-border bg-surface">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-3 lg:px-8">
          <ProofCard
            icon={Radar}
            title="The gap is not the model"
            text="Enterprises get stuck between AI ideas and production systems. Forge AI owns the people-and-plumbing gap."
          />
          <ProofCard
            icon={Workflow}
            title="Not a fixed script"
            text="Agents plan, act, observe, retry, and re-plan through a stateful LangGraph workflow."
          />
          <ProofCard
            icon={ShieldCheck}
            title="Autonomy with control"
            text="Humans approve the strategy, the schema, and the final deploy or billing step."
          />
        </div>
      </section>

      <section id="agents" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <SectionIntro
          eyebrow="Agent overview"
          title="Seven agents move one goal from sentence to endpoint."
          text="Each agent owns a narrow job, writes structured state, and hands off to the next specialist when its checkpoint is complete."
        />

        <div className="mt-8 grid gap-3 md:grid-cols-2 xl:grid-cols-7">
          {AGENTS.map((agent, index) => (
            <article key={agent.name} className="rounded-2xl border border-border bg-surface p-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-foreground">
                {index + 1}
              </div>
              <h3 className="mt-4 text-base font-bold">{agent.name}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{agent.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="stack" className="bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
          <SectionIntro
            eyebrow="Production stack"
            title="Every integration does real work in the loop."
            text="The product is designed around deployable infrastructure, live data, governed model access, and monetization from the first run."
          />

          <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {STACK.map((item) => {
              const Icon = item.icon
              return (
                <article key={item.title} className="rounded-2xl border border-border bg-background p-5">
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-info-soft text-info">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div className="mt-5 text-xl font-bold">{item.title}</div>
                  <div className="mt-1 text-sm font-semibold text-primary">{item.label}</div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.text}</p>
                </article>
              )
            })}
          </div>
        </div>
      </section>

      <section id="controls" className="mx-auto grid max-w-7xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
        <div>
          <SectionIntro
            eyebrow="Human-in-the-loop"
            title="Approval gates where correctness and spend matter."
            text="The agents run autonomously between gates. The user keeps ownership of direction, data correctness, and production spend."
          />
          <div className="mt-7 space-y-3">
            {GUARDRAILS.map((gate, index) => (
              <div key={gate.title} className="rounded-2xl border border-border bg-surface p-5">
                <div className="text-sm font-bold text-primary">Gate {index + 1}</div>
                <h3 className="mt-1 text-lg font-bold">{gate.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{gate.text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[28px] border border-border bg-surface p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-error-soft text-primary">
              <LockKeyhole className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <div className="text-sm font-bold uppercase text-primary">Failure handling</div>
              <h3 className="text-2xl font-bold">Built to recover, not just crash.</h3>
            </div>
          </div>
          <div className="mt-6 grid gap-3">
            {RECOVERY.map((item) => (
              <div key={item} className="flex items-start gap-3 rounded-2xl border border-border bg-background px-4 py-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden="true" />
                <span className="text-sm font-semibold leading-6 text-foreground">{item}</span>
              </div>
            ))}
          </div>
          <div className="mt-6 rounded-2xl bg-surface-muted p-4 text-sm leading-6 text-muted-foreground">
            Checkpointed graph state means a browser refresh, user pause, or transient API error can resume from the last completed node.
          </div>
        </div>
      </section>

      <section id="pricing" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
          <SectionIntro
            eyebrow="Commerce"
            title="Monetized through Stripe from the first production run."
            text="Subscriptions gate use cases, Exa dataset builds, RAG trials, model training, and deployment approvals."
          />
          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            {PLANS.map((plan) => (
              <article
                key={plan.name}
                className={
                  plan.featured
                    ? "rounded-2xl border border-primary bg-primary p-6 text-primary-foreground shadow-sm"
                    : "rounded-2xl border border-border bg-background p-6"
                }
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-2xl font-bold">{plan.name}</h3>
                    <p className={plan.featured ? "mt-2 text-sm text-white/85" : "mt-2 text-sm text-muted-foreground"}>
                      {plan.detail}
                    </p>
                  </div>
                  <div className="text-right text-2xl font-bold">{plan.price}</div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="rounded-[30px] border border-border bg-foreground p-6 text-background sm:p-8 lg:p-10">
          <div className="grid items-center gap-8 lg:grid-cols-[1fr_auto]">
            <div>
              <div className="text-sm font-bold uppercase text-primary">Ready to run</div>
              <h2 className="mt-3 max-w-3xl text-3xl font-bold leading-tight sm:text-4xl">
                Start with a business goal. Leave with a governed AI workflow.
              </h2>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-background/70">
                Use the live dashboard to see strategy, data generation, model workflow, retrieval, deployment readiness, billing, and settings working together.
              </p>
            </div>
            <Link
              href="/dashboard"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-primary px-5 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary-dark"
            >
              Open Forge AI
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}

function SectionIntro({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return (
    <div className="max-w-3xl">
      <div className="text-sm font-bold uppercase text-primary">{eyebrow}</div>
      <h2 className="mt-2 text-3xl font-bold leading-tight tracking-normal sm:text-4xl">{title}</h2>
      <p className="mt-4 text-sm leading-6 text-muted-foreground sm:text-base">{text}</p>
    </div>
  )
}

function ProofCard({
  icon: Icon,
  title,
  text,
}: {
  icon: React.ElementType
  title: string
  text: string
}) {
  return (
    <article className="rounded-2xl border border-border bg-background p-5">
      <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
      <h2 className="mt-4 text-xl font-bold">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
    </article>
  )
}

function ProductPreview() {
  return (
    <aside className="rounded-[30px] border border-border bg-surface p-3 shadow-sm">
      <div className="overflow-hidden rounded-[24px] border border-border bg-background">
        <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
          <div className="flex items-center gap-2.5">
            <ForgeAiIcon size="sm" priority />
            <div>
              <div className="text-sm font-bold">Forge AI Workspace</div>
              <div className="text-xs text-muted-foreground">Customer Intelligence / Churn Prediction</div>
            </div>
          </div>
          <span className="hidden rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success sm:inline-flex">
            Live run
          </span>
        </div>

        <div className="grid min-h-[34rem] lg:grid-cols-[4rem_1fr]">
          <div className="hidden border-r border-border bg-surface px-3 py-4 lg:block">
            <div className="space-y-3">
              {[Layers3, DatabaseZap, GitBranch, ShieldCheck, BadgeDollarSign].map((Icon, index) => (
                <div
                  key={index}
                  className={index === 0 ? "flex h-10 w-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground" : "flex h-10 w-10 items-center justify-center rounded-2xl bg-surface-muted text-muted-foreground"}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
              ))}
            </div>
          </div>

          <div className="p-4 sm:p-5">
            <div className="rounded-2xl bg-primary px-4 py-3 text-sm font-medium leading-6 text-primary-foreground shadow-sm">
              We lose enterprise customers after year one. Build a model that flags at-risk accounts before renewal.
            </div>

            <div className="mt-5 rounded-2xl border border-border bg-surface p-4">
              <div className="flex items-center gap-3">
                <ForgeAiIcon size="sm" />
                <div>
                  <div className="text-sm font-bold">Strategy Agent</div>
                  <div className="text-xs text-muted-foreground">Generated use cases, ROI, and feasibility</div>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <PreviewMetric label="Use cases" value="3" />
                <PreviewMetric label="Projected ROI" value="$1.4M" />
                <PreviewMetric label="Feasibility" value="High" />
              </div>
            </div>

            <div className="mt-4 overflow-hidden rounded-2xl border border-border bg-surface">
              <div className="grid grid-cols-[1.1fr_0.8fr_1fr] border-b border-border bg-surface-muted px-4 py-3 text-xs font-bold uppercase text-muted-foreground">
                <span>Use case</span>
                <span>Task</span>
                <span>Outcome</span>
              </div>
              {[
                ["Churn Prediction", "Classification", "+$1.2M ARR retained"],
                ["Expansion Propensity", "Regression", "+18% upsell rate"],
                ["Support Deflection", "Retrieval", "-32% ticket volume"],
              ].map(([name, task, outcome]) => (
                <div key={name} className="grid grid-cols-[1.1fr_0.8fr_1fr] border-b border-border px-4 py-3 text-sm last:border-b-0">
                  <span className="font-semibold">{name}</span>
                  <span className="text-primary">{task}</span>
                  <span className="text-muted-foreground">{outcome}</span>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {["Schema approval", "Model training", "Stripe billing"].map((step, index) => (
                <div key={step} className="rounded-2xl border border-border bg-surface px-4 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold">{step}</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {index === 0 ? "Waiting for human gate" : index === 1 ? "Queued on AWS" : "Plan enforced"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background px-4 py-3">
      <div className="text-2xl font-bold">{value}</div>
      <div className="mt-1 text-xs font-semibold text-muted-foreground">{label}</div>
    </div>
  )
}
