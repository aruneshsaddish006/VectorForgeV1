"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { type ElementType, type FormEvent, useState } from "react"
import {
  ArrowRight,
  BarChart3,
  Building2,
  DatabaseZap,
  LockKeyhole,
  Mail,
  ShieldCheck,
  User,
} from "lucide-react"
import { ForgeAiIcon } from "@/components/brand/forge-ai-icon"
import { ThemeToggle } from "@/components/theme-toggle"
import { continueWithGoogle, persistAuthSession, signupUser } from "@/lib/api"

const BUSINESS_CARDS = [
  {
    icon: BarChart3,
    title: "ROI-first strategy",
    text: "Rank opportunities by KPI impact and launch readiness.",
  },
  {
    icon: DatabaseZap,
    title: "Trusted data path",
    text: "Build or enrich datasets with validation built in.",
  },
  {
    icon: ShieldCheck,
    title: "Buyer-ready controls",
    text: "Track approvals, provenance, costs, and audit history.",
  },
]

export default function SignupPage() {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    const formData = new FormData(event.currentTarget)

    try {
      await signupUser({
        fullName: String(formData.get("name") || ""),
        email: String(formData.get("email") || ""),
        company: String(formData.get("company") || ""),
        password: String(formData.get("password") || ""),
      })
      window.localStorage.setItem("forge_ai_signup_email", String(formData.get("email") || ""))
      router.push("/login")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create workspace.")
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
      <AuthHeader />

      <section className="mx-auto grid h-[calc(100dvh-4rem-1px)] max-w-7xl items-center gap-5 px-4 py-4 sm:px-6 lg:grid-cols-[1fr_0.92fr] lg:px-8">
        <ValuePanel />

        <div className="flex justify-center lg:justify-end">
          <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-5 shadow-sm">
            <div>
              <div className="text-sm font-semibold text-primary">Start the workflow</div>
              <h1 className="mt-1.5 text-2xl font-semibold tracking-tight">Create your Forge AI workspace</h1>
              <p className="mt-1.5 text-sm leading-5 text-muted-foreground">
                Map your first AI opportunity and review the launch case with demo data.
              </p>
            </div>

            <form className="mt-5 space-y-3" onSubmit={handleSubmit}>
              <Field icon={User} label="Full name" name="name" placeholder="Jordan Ellis" autoComplete="name" />
              <Field
                icon={Mail}
                label="Work email"
                name="email"
                type="email"
                placeholder="name@company.com"
                autoComplete="email"
              />
              <Field
                icon={Building2}
                label="Company"
                name="company"
                placeholder="Acme Corp"
                autoComplete="organization"
              />
              <Field
                icon={LockKeyhole}
                label="Password"
                name="password"
                type="password"
                placeholder="Create a password"
                autoComplete="new-password"
              />

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
                {isSubmitting ? "Creating workspace..." : "Create workspace"}
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
                Sign up with Google
              </button>
            </form>

            <p className="mt-4 text-xs leading-5 text-muted-foreground">
              No payment required. Demo starts with mock data.
            </p>

            <p className="mt-4 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link href="/login" className="font-medium text-primary hover:underline">
                Log in
              </Link>
            </p>
          </section>
        </div>
      </section>
    </main>
  )
}

function AuthHeader() {
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
            href="/login"
            className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-foreground hover:bg-surface-muted"
          >
            Log in
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
        No consultants. No data team. Just describe the problem.
      </div>
      <h2 className="mt-4 max-w-xl text-3xl font-semibold leading-tight tracking-tight lg:text-4xl">
        Build the AI product pipeline investors want to fund.
      </h2>
      <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
        Forge AI replaces the slow handoff between strategy, data, modeling, and launch execution with one guided workspace.
      </p>

      <div className="mt-5 grid gap-2.5">
        {BUSINESS_CARDS.map((card) => {
          const Icon = card.icon
          return (
            <article key={card.title} className="rounded-xl border border-border bg-background p-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-info-soft text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                {card.title}
              </div>
              <p className="mt-1.5 text-sm leading-5 text-muted-foreground">{card.text}</p>
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
          minLength={type === "password" ? 8 : undefined}
          autoComplete={autoComplete}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
      </span>
    </label>
  )
}
