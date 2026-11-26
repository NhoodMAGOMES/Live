"use client";

import {
  Activity,
  CalendarClock,
  CheckCircle2,
  Clock,
  Play,
  RefreshCw,
  Save,
  Search,
  ToggleLeft,
  ToggleRight,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_BASE, getAgents, getAuthHeaders, type Agent } from "@/lib/api";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders()
  };
}

function statusTone(status: string | null) {
  if (status === "success") return "green" as const;
  if (status === "failed") return "red" as const;
  if (status === "skipped") return "amber" as const;
  return "blue" as const;
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString("fr-FR") : "Non disponible";
}

function formatTokens(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value);
}

type ScheduleDraft = {
  schedule_enabled: boolean;
  schedule_frequency: string;
  schedule_interval: number;
  schedule_time: string;
  schedule_weekday: number;
  config_value: number | "";
};

type SearchDraft = {
  keywords: string;
  days_back: number;
  limit: number;
  min_live_score: number;
};

const MIN_LIVE_SCORE = 25;

const defaultSearchDraft: SearchDraft = {
  keywords: [
    "programmation événementielle",
    "programmation culturelle",
    "programmation artistique",
    "exploitation événementielle",
    "gestion événementielle de site",
    "lieu culturel",
    "spectacle vivant",
    "activation de lieu",
    "commercialisation d'espaces",
    "concession culturelle",
    "DSP culturelle",
    "appel à projets culturel"
  ].join("\n"),
  days_back: 14,
  limit: 300,
  min_live_score: MIN_LIVE_SCORE
};

function configKey(agent: Agent) {
  if (Object.prototype.hasOwnProperty.call(agent.config, "max_items_per_run")) return "max_items_per_run";
  if (Object.prototype.hasOwnProperty.call(agent.config, "deadline_days")) return "deadline_days";
  return null;
}

function configLabel(key: string | null) {
  if (key === "max_items_per_run") return "Max/run";
  if (key === "deadline_days") return "Jours deadline";
  return "Paramètre";
}

function draftFromAgent(agent: Agent): ScheduleDraft {
  const key = configKey(agent);
  const rawValue = key ? Number(agent.config[key] ?? "") : "";
  return {
    schedule_enabled: agent.schedule_enabled,
    schedule_frequency: agent.schedule_frequency,
    schedule_interval: agent.schedule_interval,
    schedule_time: agent.schedule_time,
    schedule_weekday: agent.schedule_weekday,
    config_value: Number.isFinite(rawValue) ? rawValue : ""
  };
}

function searchDraftFromAgent(agent: Agent | undefined): SearchDraft {
  if (!agent) return defaultSearchDraft;
  const config = agent.config || {};
  const keywords = Array.isArray(config.keywords) ? config.keywords.join("\n") : defaultSearchDraft.keywords;
  return {
    keywords,
    days_back: Number(config.days_back || defaultSearchDraft.days_back),
    limit: Math.min(1000, Math.max(1, Number(config.limit || defaultSearchDraft.limit))),
    min_live_score: Math.max(MIN_LIVE_SCORE, Number(config.min_live_score || defaultSearchDraft.min_live_score))
  };
}

function parseKeywords(value: string) {
  return value
    .split(/[\n,;]+/)
    .map((keyword) => keyword.trim())
    .filter(Boolean);
}

function clampSearchDraft(draft: SearchDraft) {
  return {
    ...draft,
    days_back: Math.max(1, Number(draft.days_back || 14)),
    limit: Math.min(1000, Math.max(1, Number(draft.limit || defaultSearchDraft.limit))),
    min_live_score: Math.max(MIN_LIVE_SCORE, Number(draft.min_live_score || MIN_LIVE_SCORE))
  };
}

export function AgentConsole() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [drafts, setDrafts] = useState<Record<string, ScheduleDraft>>({});
  const [searchDraft, setSearchDraft] = useState<SearchDraft>(defaultSearchDraft);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const nextAgents = await getAgents();
      setAgents(nextAgents);
      setDrafts(Object.fromEntries(nextAgents.map((agent) => [agent.slug, draftFromAgent(agent)])));
      setSearchDraft(searchDraftFromAgent(nextAgents.find((agent) => agent.slug === "source_discovery")));
      setError(null);
    } catch (caught) {
      setAgents([]);
      setDrafts({});
      const message = caught instanceof Error ? caught.message : "";
      setError(message.startsWith("401") || message.startsWith("403") ? "Session expirée ou accès backoffice non autorisé. Reconnectez-vous avec un profil admin." : "Impossible de charger les agents.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const totals = useMemo(
    () => ({
      runs: agents.reduce((sum, agent) => sum + agent.stats.run_count, 0),
      tokens: agents.reduce((sum, agent) => sum + agent.stats.total_tokens, 0),
      active: agents.filter((agent) => agent.is_active).length
    }),
    [agents]
  );

  async function toggle(agent: Agent) {
    setBusy(agent.slug);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/agents/${agent.slug}`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({ is_active: !agent.is_active })
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      await refresh();
    } catch {
      setError("Action impossible. Vérifiez votre session admin.");
    } finally {
      setBusy(null);
    }
  }

  function updateDraft(slug: string, patch: Partial<ScheduleDraft>) {
    setDrafts((current) => ({ ...current, [slug]: { ...current[slug], ...patch } }));
  }

  async function saveSettings(agent: Agent) {
    const draft = drafts[agent.slug] || draftFromAgent(agent);
    const key = configKey(agent);
    const nextConfig = { ...agent.config };
    if (key && draft.config_value !== "") nextConfig[key] = Number(draft.config_value);
    setBusy(agent.slug);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/agents/${agent.slug}`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({
          config: nextConfig,
          schedule_enabled: draft.schedule_enabled,
          schedule_frequency: draft.schedule_enabled ? draft.schedule_frequency : "manual",
          schedule_interval: Number(draft.schedule_interval || 1),
          schedule_time: draft.schedule_time || "08:00",
          schedule_weekday: Number(draft.schedule_weekday || 0)
        })
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      await refresh();
    } catch {
      setError("Paramètres non enregistrés. Vérifiez votre session admin.");
    } finally {
      setBusy(null);
    }
  }

  async function run(agent: Agent) {
    setBusy(agent.slug);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/agents/${agent.slug}/run`, { method: "POST", headers: getAuthHeaders() });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      await refresh();
    } catch {
      setError("Lancement impossible. Vérifiez votre session admin.");
    } finally {
      setBusy(null);
    }
  }

  async function runKeywordSearch() {
    const safeDraft = clampSearchDraft(searchDraft);
    setBusy("source_discovery_search");
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/agents/source_discovery/run`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          config_override: {
            keywords: parseKeywords(safeDraft.keywords),
            days_back: safeDraft.days_back,
            limit: safeDraft.limit,
            min_live_score: safeDraft.min_live_score,
            prequalification_enabled: true
          }
        })
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      await refresh();
    } catch {
      setError("Recherche non lancée. Reconnectez-vous avec un profil admin.");
    } finally {
      setBusy(null);
    }
  }

  async function saveKeywordSearchConfig() {
    const agent = agents.find((item) => item.slug === "source_discovery");
    if (!agent) return;
    const safeDraft = clampSearchDraft(searchDraft);
    setBusy("source_discovery_search");
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/agents/source_discovery`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({
          config: {
            ...agent.config,
            keywords: parseKeywords(safeDraft.keywords),
            days_back: safeDraft.days_back,
            limit: safeDraft.limit,
            min_live_score: safeDraft.min_live_score,
            prequalification_enabled: true
          }
        })
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      await refresh();
    } catch {
      setError("Configuration non enregistrée. Reconnectez-vous avec un profil admin.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error && <div className="rounded-md border border-danger/20 bg-danger-light p-3 text-sm text-danger">{error}</div>}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-foreground/60">Agents actifs</span>
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-3 text-3xl font-semibold">{totals.active}/{agents.length}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-foreground/60">Runs totaux</span>
            <CheckCircle2 className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-3 text-3xl font-semibold">{totals.runs}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-foreground/60">Tokens directs</span>
            <Clock className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-3 text-3xl font-semibold">{formatTokens(totals.tokens)}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-foreground/60">Planifiés</span>
            <CalendarClock className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-3 text-3xl font-semibold">{agents.filter((agent) => agent.schedule_enabled).length}</div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Recherche manuelle plateformes</h2>
            </div>
            <p className="mt-1 max-w-3xl text-sm text-foreground/60">
              Lance l'agent de recherche avec une intention LIVE: événementiel, lieux vivants, programmation, exploitation, commercialisation d'espaces et stratégie de lieu.
            </p>
          </div>
          <Badge tone="blue">Agent Recherche plateformes LIVE</Badge>
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
          <label className="block text-sm font-medium">
            Mots-clés de recherche
            <textarea
              value={searchDraft.keywords}
              onChange={(event) => setSearchDraft((current) => ({ ...current, keywords: event.target.value }))}
              rows={7}
              className="mt-2 w-full"
              placeholder="Un mot-clé ou une expression par ligne"
            />
          </label>
          <div className="grid gap-3">
            <label className="block text-xs text-foreground/60">
              Jours à regarder
              <input
                type="number"
                min={1}
                value={searchDraft.days_back}
                onChange={(event) => setSearchDraft((current) => ({ ...current, days_back: Number(event.target.value || 14) }))}
                className="mt-1 w-full"
              />
            </label>
            <label className="block text-xs text-foreground/60">
              Limite par plateforme
              <input
                type="number"
                min={1}
                max={1000}
                value={searchDraft.limit}
                onChange={(event) => setSearchDraft((current) => ({ ...current, limit: Number(event.target.value || defaultSearchDraft.limit) }))}
                className="mt-1 w-full"
              />
            </label>
            <label className="block text-xs text-foreground/60">
              Score LIVE minimum à importer
              <input
                type="number"
                min={MIN_LIVE_SCORE}
                max={100}
                value={searchDraft.min_live_score}
                onChange={(event) => setSearchDraft((current) => ({ ...current, min_live_score: Math.max(MIN_LIVE_SCORE, Number(event.target.value || MIN_LIVE_SCORE)) }))}
                className="mt-1 w-full"
              />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button onClick={runKeywordSearch} disabled={busy === "source_discovery_search"}>
                <Play className="h-4 w-4" />
                Lancer
              </Button>
              <Button onClick={saveKeywordSearchConfig} disabled={busy === "source_discovery_search"} variant="secondary">
                <Save className="h-4 w-4" />
                Sauver
              </Button>
            </div>
            <p className="text-xs leading-5 text-foreground/60">
              Pour l'automatique, sauve ces paramètres puis règle le timing dans la ligne de l'agent.
            </p>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
          <h2 className="text-sm font-semibold">Agents</h2>
          <Button onClick={refresh} variant="secondary" size="sm">
            <RefreshCw className="h-4 w-4" />
            Actualiser
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Agent</th>
                <th>Planification</th>
                <th>Paramètre</th>
                <th>Activité</th>
                <th>Réussite</th>
                <th>Tokens</th>
                <th>Dernier run</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => {
                const draft = drafts[agent.slug] || draftFromAgent(agent);
                const key = configKey(agent);
                return (
                  <tr key={agent.slug}>
                    <td className="max-w-sm">
                      <div className="font-medium">{agent.name}</div>
                      <div className="mt-1 text-xs text-foreground/60">{agent.description}</div>
                      <div className="mt-2 text-xs text-foreground/70">{agent.task}</div>
                    </td>
                    <td className="min-w-[320px]">
                      <div className="flex flex-wrap items-center gap-2">
                        <label className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-2 text-xs">
                          <input
                            type="checkbox"
                            checked={draft.schedule_enabled}
                            onChange={(event) => updateDraft(agent.slug, { schedule_enabled: event.target.checked })}
                          />
                          Auto
                        </label>
                        <select
                          value={draft.schedule_frequency}
                          onChange={(event) => updateDraft(agent.slug, { schedule_frequency: event.target.value })}
                          className="h-9 w-28"
                          disabled={!draft.schedule_enabled}
                        >
                          <option value="manual">Manuel</option>
                          <option value="hourly">Heures</option>
                          <option value="daily">Jours</option>
                          <option value="weekly">Semaines</option>
                        </select>
                        <input
                          type="number"
                          min={1}
                          value={draft.schedule_interval}
                          onChange={(event) => updateDraft(agent.slug, { schedule_interval: Number(event.target.value || 1) })}
                          className="h-9 w-20"
                          disabled={!draft.schedule_enabled}
                        />
                        {draft.schedule_frequency !== "hourly" && (
                          <input
                            type="time"
                            value={draft.schedule_time}
                            onChange={(event) => updateDraft(agent.slug, { schedule_time: event.target.value })}
                            className="h-9 w-28"
                            disabled={!draft.schedule_enabled}
                          />
                        )}
                        {draft.schedule_frequency === "weekly" && (
                          <select
                            value={draft.schedule_weekday}
                            onChange={(event) => updateDraft(agent.slug, { schedule_weekday: Number(event.target.value) })}
                            className="h-9 w-28"
                            disabled={!draft.schedule_enabled}
                          >
                            <option value={0}>Lundi</option>
                            <option value={1}>Mardi</option>
                            <option value={2}>Mercredi</option>
                            <option value={3}>Jeudi</option>
                            <option value={4}>Vendredi</option>
                            <option value={5}>Samedi</option>
                            <option value={6}>Dimanche</option>
                          </select>
                        )}
                      </div>
                      <div className="mt-2 text-xs text-foreground/60">Prochain: {formatDate(agent.next_run_at)}</div>
                    </td>
                    <td>
                      {key ? (
                        <label className="block text-xs text-foreground/60">
                          {configLabel(key)}
                          <input
                            type="number"
                            min={1}
                            value={draft.config_value}
                            onChange={(event) =>
                              updateDraft(agent.slug, { config_value: event.target.value ? Number(event.target.value) : "" })
                            }
                            className="mt-1 h-9 w-24"
                          />
                        </label>
                      ) : (
                        <span className="text-sm text-foreground/60">Standard</span>
                      )}
                    </td>
                    <td>
                      <button onClick={() => toggle(agent)} disabled={busy === agent.slug}>
                        <Badge tone={agent.is_active ? "green" : "neutral"}>
                          {agent.is_active ? <ToggleRight className="mr-1 h-3.5 w-3.5" /> : <ToggleLeft className="mr-1 h-3.5 w-3.5" />}
                          {agent.is_active ? "Actif" : "Inactif"}
                        </Badge>
                      </button>
                    </td>
                    <td>
                      <div className="font-medium">{agent.stats.success_rate}%</div>
                      <div className="text-xs text-foreground/60">
                        {agent.stats.success_count} ok / {agent.stats.failure_count} échec
                      </div>
                    </td>
                    <td>
                      <div className="font-medium">{formatTokens(agent.stats.total_tokens)}</div>
                      <div className="text-xs text-foreground/60">
                        in {formatTokens(agent.stats.input_tokens)} / out {formatTokens(agent.stats.output_tokens)}
                      </div>
                      {agent.stats.orchestrated_tokens ? (
                        <div className="text-xs text-foreground/60">
                          orchestré {formatTokens(agent.stats.orchestrated_tokens)} non additionné
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <Badge tone={statusTone(agent.stats.last_status)}>{agent.stats.last_status || "Jamais"}</Badge>
                      <div className="mt-1 text-xs text-foreground/60">{formatDate(agent.last_run_at)}</div>
                    </td>
                    <td>
                      <div className="flex flex-col gap-2">
                        <Button onClick={() => saveSettings(agent)} disabled={busy === agent.slug} size="sm" variant="secondary">
                          <Save className="h-4 w-4" />
                          Sauver
                        </Button>
                        <Button onClick={() => run(agent)} disabled={busy === agent.slug || !agent.is_active} size="sm">
                          <Play className="h-4 w-4" />
                          Lancer
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {!agents.length && (
                <tr>
                  <td colSpan={8} className="text-sm text-foreground/60">
                    Aucun agent.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        {agents.map((agent) => (
          <Card key={`${agent.slug}-runs`} className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-border p-4">
              <h3 className="text-sm font-semibold">{agent.name}</h3>
              <Badge tone={agent.is_active ? "green" : "neutral"}>{agent.is_active ? "Actif" : "Inactif"}</Badge>
            </div>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Statut</th>
                    <th>Entrées</th>
                    <th>Sorties</th>
                    <th>Tokens</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {agent.recent_runs.map((run) => (
                    <tr key={run.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          {run.status === "failed" ? (
                            <XCircle className="h-4 w-4 text-danger" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4 text-primary" />
                          )}
                          <span>{run.status}</span>
                        </div>
                        {run.error_message && <div className="mt-1 max-w-xs text-xs text-danger">{run.error_message}</div>}
                      </td>
                      <td>{run.input_count}</td>
                      <td>{run.output_count}</td>
                      <td>
                        {agent.stats.orchestrated_tokens ? `${formatTokens(run.total_tokens)} orchestrés` : formatTokens(run.total_tokens)}
                      </td>
                      <td>{formatDate(run.started_at)}</td>
                    </tr>
                  ))}
                  {!agent.recent_runs.length && (
                    <tr>
                      <td colSpan={5} className="text-sm text-foreground/60">
                        Aucun run.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
