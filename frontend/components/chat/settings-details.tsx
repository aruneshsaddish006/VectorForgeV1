"use client"

import * as React from "react"
import {
  CheckCircle2,
  Cloud,
  CreditCard,
  Database,
  KeyRound,
  Loader2,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  TestTube2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  fetchWorkspaceSettings,
  saveProviderSettings,
  testProviderSettings,
  type IntegrationProviderSettings,
  type Workspace,
  type WorkspaceSettings,
} from "@/lib/api"
import { cn } from "@/lib/utils"

const PROVIDER_ICONS: Record<string, React.ElementType> = {
  exa: Search,
  vercel_ai: Sparkles,
  openai: KeyRound,
  stripe: CreditCard,
  aws: Cloud,
}

type DraftState = Record<
  string,
  {
    enabled: boolean
    config: Record<string, string>
    secrets: Record<string, string>
  }
>

export function SettingsDetails({ selectedWorkspace }: { selectedWorkspace: Workspace | null }) {
  const [settings, setSettings] = React.useState<WorkspaceSettings | null>(null)
  const [drafts, setDrafts] = React.useState<DraftState>({})
  const [loading, setLoading] = React.useState(false)
  const [savingProvider, setSavingProvider] = React.useState<string | null>(null)
  const [testingProvider, setTestingProvider] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [notice, setNotice] = React.useState<string | null>(null)

  const loadSettings = React.useCallback(async () => {
    if (!selectedWorkspace) {
      setSettings(null)
      setDrafts({})
      return
    }
    setLoading(true)
    setError(null)
    try {
      const nextSettings = await fetchWorkspaceSettings(selectedWorkspace.id)
      setSettings(nextSettings)
      setDrafts(buildDrafts(nextSettings.providers))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load settings.")
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspace?.id])

  React.useEffect(() => {
    loadSettings()
  }, [loadSettings])

  function updateConfig(providerId: string, key: string, value: string) {
    setDrafts((current) => ({
      ...current,
      [providerId]: {
        ...current[providerId],
        config: { ...(current[providerId]?.config ?? {}), [key]: value },
      },
    }))
  }

  function updateSecret(providerId: string, key: string, value: string) {
    setDrafts((current) => ({
      ...current,
      [providerId]: {
        ...current[providerId],
        secrets: { ...(current[providerId]?.secrets ?? {}), [key]: value },
      },
    }))
  }

  function updateEnabled(providerId: string, enabled: boolean) {
    setDrafts((current) => ({
      ...current,
      [providerId]: { ...current[providerId], enabled },
    }))
  }

  async function handleSave(provider: IntegrationProviderSettings) {
    if (!selectedWorkspace) return
    const draft = drafts[provider.id]
    setSavingProvider(provider.id)
    setError(null)
    setNotice(null)
    try {
      const updated = await saveProviderSettings({
        workspaceId: selectedWorkspace.id,
        provider: provider.id,
        enabled: draft?.enabled ?? provider.enabled,
        config: draft?.config ?? provider.config,
        secrets: compactSecrets(draft?.secrets ?? {}),
      })
      setSettings((current) =>
        current
          ? {
              ...current,
              providers: current.providers.map((item) => (item.id === updated.id ? updated : item)),
            }
          : current,
      )
      setDrafts((current) => ({
        ...current,
        [provider.id]: { enabled: updated.enabled, config: updated.config, secrets: {} },
      }))
      setNotice(`${updated.name} settings saved.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings.")
    } finally {
      setSavingProvider(null)
    }
  }

  async function handleTest(provider: IntegrationProviderSettings) {
    if (!selectedWorkspace) return
    const draft = drafts[provider.id]
    setTestingProvider(provider.id)
    setError(null)
    setNotice(null)
    try {
      const result = await testProviderSettings({
        workspaceId: selectedWorkspace.id,
        provider: provider.id,
        config: draft?.config ?? provider.config,
        secrets: compactSecrets(draft?.secrets ?? {}),
      })
      setNotice(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Provider validation failed.")
    } finally {
      setTestingProvider(null)
    }
  }

  if (!selectedWorkspace) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="app-panel-raised max-w-2xl rounded-[28px] p-8 text-center">
          <ShieldCheck className="mx-auto h-8 w-8 text-primary" aria-hidden="true" />
          <h1 className="mt-4 font-heading text-3xl font-bold">Select a workspace</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Integration settings are stored per workspace.
          </p>
        </div>
      </div>
    )
  }

  const providers = settings?.providers ?? []
  const configuredCount = providers.filter((provider) => provider.configured).length

  return (
    <div className="scroll-thin h-full overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <section className="app-panel-raised rounded-[30px] p-6 sm:p-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Workspace Settings</p>
              <h1 className="mt-3 font-heading text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Integrations
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                Configure the live keys used by agents for web data, model routing, storage, and billing.
              </p>
            </div>
            <div className="app-control rounded-2xl px-4 py-3">
              <div className="text-xs font-medium text-muted-foreground">Workspace</div>
              <div className="mt-1 max-w-64 truncate text-lg font-bold text-foreground">{selectedWorkspace.name}</div>
              <div className="mt-2 text-xs text-muted-foreground">
                {loading ? "Loading settings..." : `${configuredCount} of ${providers.length} providers configured`}
              </div>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="outline" onClick={loadSettings} disabled={loading} className="rounded-full">
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
              Refresh
            </Button>
            <span className="inline-flex items-center gap-2 rounded-full bg-info-soft px-3 py-1.5 text-xs font-bold text-info">
              <Database className="h-3.5 w-3.5" aria-hidden="true" />
              Stored in Postgres
            </span>
          </div>
        </section>

        {error && (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error" role="alert">
            {error}
          </div>
        )}
        {notice && (
          <div className="rounded-2xl border border-success/30 bg-success-soft px-4 py-3 text-sm font-medium text-success" role="status">
            {notice}
          </div>
        )}

        <section className="grid gap-4">
          {providers.map((provider) => {
            const draft = drafts[provider.id] ?? { enabled: provider.enabled, config: provider.config, secrets: {} }
            const Icon = PROVIDER_ICONS[provider.id] ?? KeyRound
            const saving = savingProvider === provider.id
            const testing = testingProvider === provider.id

            return (
              <article key={provider.id} className="app-panel-raised rounded-[28px] p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex min-w-0 gap-4">
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <Icon className="h-6 w-6" aria-hidden="true" />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="font-heading text-2xl font-bold text-foreground">{provider.name}</h2>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold",
                            provider.configured ? "bg-success-soft text-success" : "bg-warning-soft text-warning",
                          )}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                          {provider.configured ? "Configured" : "Needs setup"}
                        </span>
                      </div>
                      <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">{provider.description}</p>
                    </div>
                  </div>

                  <label className="flex w-fit items-center gap-2 rounded-full bg-surface-muted px-3 py-2 text-sm font-semibold text-foreground">
                    <input
                      type="checkbox"
                      checked={draft.enabled}
                      onChange={(event) => updateEnabled(provider.id, event.target.checked)}
                      className="h-4 w-4 accent-[var(--primary)]"
                    />
                    Enabled
                  </label>
                </div>

                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  <div className="space-y-3">
                    <h3 className="text-sm font-bold uppercase tracking-[0.16em] text-muted-foreground">Configuration</h3>
                    {provider.configFields.map((field) => (
                      <label key={field.key} className="block">
                        <span className="text-sm font-semibold text-foreground">{field.label}</span>
                        <input
                          value={draft.config[field.key] ?? ""}
                          onChange={(event) => updateConfig(provider.id, field.key, event.target.value)}
                          className="app-control mt-1.5 h-11 w-full rounded-2xl px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                          placeholder={field.label}
                        />
                      </label>
                    ))}
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-bold uppercase tracking-[0.16em] text-muted-foreground">Secrets</h3>
                    {provider.secretFields.map((field) => (
                      <label key={field.key} className="block">
                        <span className="flex items-center justify-between gap-3 text-sm font-semibold text-foreground">
                          {field.label}
                          <span className="text-xs font-medium text-muted-foreground">
                            {field.configured ? `${field.masked} · ${field.source}` : "Not configured"}
                          </span>
                        </span>
                        <input
                          type="password"
                          value={draft.secrets[field.key] ?? ""}
                          onChange={(event) => updateSecret(provider.id, field.key, event.target.value)}
                          className="app-control mt-1.5 h-11 w-full rounded-2xl px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                          placeholder={field.configured ? "Leave blank to keep existing value" : "Enter key"}
                          autoComplete="off"
                        />
                      </label>
                    ))}
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap justify-end gap-2">
                  <Button variant="outline" onClick={() => handleTest(provider)} disabled={testing || saving} className="rounded-full">
                    {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 className="h-4 w-4" />}
                    Test connection
                  </Button>
                  <Button onClick={() => handleSave(provider)} disabled={saving || testing} className="rounded-full">
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save settings
                  </Button>
                </div>
              </article>
            )
          })}
        </section>
      </div>
    </div>
  )
}

function buildDrafts(providers: IntegrationProviderSettings[]): DraftState {
  return providers.reduce<DraftState>((acc, provider) => {
    acc[provider.id] = {
      enabled: provider.enabled,
      config: provider.config,
      secrets: {},
    }
    return acc
  }, {})
}

function compactSecrets(secrets: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(secrets).filter(([, value]) => value.trim().length > 0))
}
