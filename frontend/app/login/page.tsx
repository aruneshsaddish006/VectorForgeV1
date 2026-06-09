"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { type ElementType, type FormEvent, useState } from "react"
import { ArrowRight, BarChart3, DatabaseZap, LockKeyhole, Mail, ShieldCheck } from "lucide-react"
import { ForgeAiIcon } from "@/components/brand/forge-ai-icon"
import { ThemeToggle } from "@/components/theme-toggle"
import { continueWithGoogle, loginUser, persistAuthSession } from "@/lib/api"

const PROOF_POINTS = [
  {
    icon: BarChart3,
    label: "Strategy workspace",
    value: "Review use cases, ROI, KPIs, and launch priorities.",
  },
  {
    icon: DatabaseZap,
    label: "Data and model status",
    value: "Track dataset readiness, model runs, and launch progress.",
  },
  {
    icon: ShieldCheck,
    label: "Enterprise controls",
    value: "Keep approvals, provenance, cost gates, and audit history visible.",
  },
]

export default function LoginPage() {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    const formData = new FormData(event.currentTarget)

    try {
      const auth = await loginUser({
        email: String(formData.get("email") || ""),
        password: String(formData.get("password") || ""),
      })
      persistAuthSession(auth)
      router.push("/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log in.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleGoogleAuth() {
    setError(null)
    setIsSubmitting(true)

    try {
      const auth = await continueWithGoogle()
      persistAuthSession(auth)
      router.push("/dashboard")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not continue with Google.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-dvh overflow-hidden bg-canvas text-foreground">
      <AuthHeader ctaHref="/signup" ctaLabel="Create account" />

      <section className="mx-auto grid h-[calc(100dvh-4rem-1px)] max-w-7xl items-center gap-5 px-4 py-4 sm:px-6 lg:grid-cols-[0.95fr_1.05fr] lg:px-8">
        <ValuePanel />

        <div className="flex justify-center lg:justify-end">
          <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-sm">
            <div>
              <div className="text-sm font-semibold text-primary">Welcome back</div>
              <h1 className="mt-1.5 text-2xl font-semibold tracking-tight">Log in to Forge AI</h1>
              <p className="mt-1.5 text-sm leading-5 text-muted-foreground">
                Continue your AI product workflow and review strategy, data, approvals, and launch progress.
              </p>
            </div>

            <form className="mt-5 space-y-3" onSubmit={handleSubmit}>
              <Field
                icon={Mail}
                label="Work email"
                name="email"
                type="email"
                placeholder="name@company.com"
                autoComplete="email"
              />

              <label className="block">
                <span className="flex items-center justify-between text-sm font-medium text-foreground">
                  Password
                  <a href="#" className="text-xs font-medium text-primary hover:underline">
                    Forgot password?
                  </a>
                </span>
                <span className="mt-1 flex h-10 items-center gap-2 rounded-lg border border-border bg-surface-muted/60 px-3 focus-within:border-primary">
                  <LockKeyhole className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <input
                    type="password"
                    name="password"
                    required
                    autoComplete="current-password"
                    placeholder="Enter your password"
                    className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                  />
                </span>
              </label>

              {error && (
                <div className="rounded-lg border border-error/30 bg-error-soft px-3 py-2 text-sm text-error" role="alert">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary-dark"
              >
                {isSubmitting ? "Logging in..." : "Open workspace"}
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>

              <div className="flex items-center gap-3">
                <span className="h-px flex-1 bg-border" />
                <span className="text-xs font-medium text-muted-foreground">or</span>
                <span className="h-px flex-1 bg-border" />
              </div>

              <button
                type="button"
                onClick={handleGoogleAuth}
                disabled={isSubmitting}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-5 text-sm font-medium text-foreground hover:bg-surface-muted"
              >
                <span className="font-heading text-base font-semibold text-primary">G</span>
                Continue with Google
              </button>
            </form>

            <p className="mt-4 text-center text-sm text-muted-foreground">
              New to Forge AI?{" "}
              <Link href="/signup" className="font-medium text-primary hover:underline">
                Create an account
              </Link>
            </p>
          </section>
        </div>
      </section>
    </main>
  )
}

function AuthHeader({ ctaHref, ctaLabel }: { ctaHref: string; ctaLabel: string }) {
  return (
    <header className="border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="inline-flex items-center gap-2.5" aria-label="Forge AI home">
          <ForgeAiIcon size="md" priority />
          <span className="font-heading text-lg font-semibold">Forge AI</span>
        </Link>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href={ctaHref}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground hover:bg-surface-muted"
          >
            {ctaLabel}
          </Link>
        </div>
      </div>
    </header>
  )
}

function ValuePanel() {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm lg:p-6">
      <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1 text-xs font-medium text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
        Enterprise AI launch control
      </div>
      <h2 className="mt-4 max-w-xl text-3xl font-semibold leading-tight tracking-tight lg:text-4xl">
        From business problem to production AI — in one conversation.
      </h2>
      <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
        Describe your goal and KPIs. Forge AI agents craft the strategy, build the data, train the models, and prepare launch.
      </p>

      <div className="mt-5 grid gap-2.5">
        {PROOF_POINTS.map((item) => {
          const Icon = item.icon
          return (
            <article key={item.label} className="rounded-xl border border-border bg-background p-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-info-soft text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                {item.label}
              </div>
              <p className="mt-1.5 text-sm leading-5 text-muted-foreground">{item.value}</p>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function Field({
  icon: Icon,
  label,
  name,
  type = "text",
  placeholder,
  autoComplete,
}: {
  icon: ElementType
  label: string
  name: string
  type?: string
  placeholder: string
  autoComplete: string
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground">{label}</span>
      <span className="mt-1 flex h-10 items-center gap-2 rounded-lg border border-border bg-surface-muted/60 px-3 focus-within:border-primary">
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <input
          type={type}
          name={name}
          required
          autoComplete={autoComplete}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
      </span>
    </label>
  )
}
