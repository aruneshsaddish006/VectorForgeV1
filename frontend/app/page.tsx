import Link from "next/link"
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  DatabaseZap,
  Layers3,
  Rocket,
  ShieldCheck,
  Sparkles,
} from "lucide-react"

const FLOW = [
  {
    title: "Describe the business goal",
    text: "Enter the problem, KPIs, customer segment, and timeline in plain language.",
  },
  {
    title: "Agents do the heavy lift",
    text: "Forge AI defines the strategy, builds the data, validates quality, and prepares the model workflow.",
  },
  {
    title: "Approve and launch",
    text: "Review ROI, provenance, costs, approvals, and deployment readiness before production.",
  },
]

const FEATURES = [
  {
    icon: BarChart3,
    title: "Strategy without consultants",
    text: "Turn a plain-language business problem into use cases, ROI logic, feasibility, and next steps.",
  },
  {
    icon: DatabaseZap,
    title: "Data without a data team",
    text: "Create trusted datasets from uploads, web research, or enrichment when teams lack clean training data.",
  },
  {
    icon: Layers3,
    title: "Execution without handoffs",
    text: "Move from strategy to model workflow to launch readiness in one workspace instead of scattered tools.",
  },
  {
    icon: ShieldCheck,
    title: "Controls buyers expect",
    text: "Keep approvals, provenance, costs, deployment readiness, and audit history visible.",
  },
]

const PROOF = [
  { label: "Dataset rows", value: "180" },
  { label: "Quality score", value: "92" },
  { label: "Launch gates", value: "3" },
]

export default function HomePage() {
  return (
    <main className="min-h-dvh bg-canvas text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5" aria-label="Forge AI home">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="font-heading text-lg font-semibold tracking-tight">Forge AI</span>
          </Link>

          <nav className="hidden items-center gap-6 text-sm font-medium text-muted-foreground md:flex">
            <a href="#how-it-works" className="hover:text-foreground">How it works</a>
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#enterprise" className="hover:text-foreground">Enterprise</a>
          </nav>

          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="hidden rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-surface-muted hover:text-foreground sm:inline-flex"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="inline-flex h-9 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary-dark"
            >
              Sign up
            </Link>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1fr_0.85fr] lg:px-8 lg:py-20">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted-foreground">
            <Rocket className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            No consultants. No data team. Just describe the problem.
          </div>
          <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-[1.02] tracking-tight sm:text-5xl lg:text-6xl">
            From business problem to production AI — in one conversation.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Forge AI replaces the strategy consultant, data analyst, and data science handoff with agents that craft the
            strategy, build the data, train the models, and prepare the system for launch.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/signup"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary-dark"
            >
              Create workspace
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex h-11 items-center justify-center rounded-lg border border-border bg-surface px-5 text-sm font-medium text-foreground hover:bg-surface-muted"
            >
              View live demo
            </Link>
          </div>

          <div className="mt-8 flex flex-wrap gap-2 text-xs font-medium text-muted-foreground">
            {["Strategy", "Data", "Models", "Approvals", "Launch"].map((item) => (
              <span key={item} className="rounded-full border border-border bg-surface px-3 py-1">
                {item}
              </span>
            ))}
          </div>
        </div>

        <ProductSnapshot />
      </section>

      <section id="how-it-works" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <div className="text-sm font-semibold text-primary">How it works</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">A clear path from problem to product.</h2>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {FLOW.map((step, index) => (
              <article key={step.title} className="rounded-xl border border-border bg-background p-5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-info-soft font-mono text-sm font-semibold text-primary">
                  {index + 1}
                </div>
                <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.78fr_1.22fr]">
          <div>
            <div className="text-sm font-semibold text-primary">Product focus</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Replace months of consulting and hiring with one operating workflow.</h2>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">
              Forge AI is not another model builder. It owns the full arc from business intent to data, model workflow,
              approvals, and launch readiness.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {FEATURES.map((feature) => {
              const Icon = feature.icon
              return (
                <article key={feature.title} className="rounded-xl border border-border bg-surface p-5">
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-info-soft text-primary">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{feature.text}</p>
                </article>
              )
            })}
          </div>
        </div>
      </section>

      <section id="enterprise" className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm sm:p-8">
          <div className="grid items-center gap-8 lg:grid-cols-[1fr_auto]">
            <div>
              <div className="text-sm font-semibold text-primary">Ready for enterprise evaluation</div>
              <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight">
                Show a complete AI product workflow without hiring the team first.
              </h2>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-muted-foreground">
                Use the demo workspace to see how business intake, data generation, schema review, model workflow,
                deployment readiness, billing approvals, and activity logs fit together.
              </p>
            </div>
            <Link
              href="/dashboard"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary-dark"
            >
              Open demo
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}

function ProductSnapshot() {
  return (
    <aside className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <div className="rounded-xl border border-border bg-surface-muted/60 p-4">
        <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
          <div>
            <div className="text-xs font-medium text-muted-foreground">Workspace preview</div>
            <h2 className="mt-1 text-xl font-semibold">Churn prediction launch plan</h2>
          </div>
          <span className="rounded-full border border-success/30 bg-success-soft px-2.5 py-1 text-xs font-medium text-success">
            Ready
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2.5">
          {PROOF.map((item) => (
            <div key={item.label} className="rounded-lg border border-border bg-surface px-3 py-3">
              <div className="font-mono text-lg font-semibold">{item.value}</div>
              <div className="mt-1 text-[11px] leading-snug text-muted-foreground">{item.label}</div>
            </div>
          ))}
        </div>

        <div className="mt-4 space-y-2">
          {[
            ["Strategy", "Retention KPI mapped to churn prediction"],
            ["Data", "Structured dataset generated and validated"],
            ["Control", "Schema, cost, and deployment approvals queued"],
          ].map(([label, text]) => (
            <div key={label} className="flex gap-3 rounded-lg border border-border bg-surface px-3 py-3">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
              <div>
                <div className="text-sm font-semibold">{label}</div>
                <div className="mt-0.5 text-xs leading-5 text-muted-foreground">{text}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
