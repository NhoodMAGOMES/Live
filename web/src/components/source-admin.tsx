"use client";

import { CheckCircle2, Loader2, Play, Plus, RefreshCw, XCircle } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  API_BASE,
  getAuthHeaders,
  getSourceRuns,
  getSourceRunTaskStatus,
  getSources,
  runSource as launchSource,
  type Source,
  type SourceRun
} from "@/lib/api";

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function authHeaders() {
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders()
  };
}

function runTone(status?: string) {
  if (status === "success") return "green" as const;
  if (status === "failed") return "red" as const;
  if (status === "running") return "blue" as const;
  return "neutral" as const;
}

function connectionLabel(source: Source) {
  const status = String(source.config.connection_status || "");
  if (status === "connected") return { label: "Connecté", tone: "green" as const };
  if (status === "requires_agreement") return { label: "Accès éditeur requis", tone: "amber" as const };
  if (status === "reference_only") return { label: "Enrichissement", tone: "blue" as const };
  return { label: source.is_active ? "Configuré" : "À configurer", tone: "neutral" as const };
}

function durationLabel(run?: SourceRun) {
  if (!run?.started_at) return null;
  const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(run.started_at).getTime()) / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${seconds % 60} s`;
}

export function SourceAdmin() {
  const [sources, setSources] = useState<Source[]>([]);
  const [runsBySource, setRunsBySource] = useState<Record<number, SourceRun[]>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  async function refresh() {
    const nextSources = await getSources();
    setSources(nextSources);
    const runEntries = await Promise.all(
      nextSources.map(async (source) => {
        try {
          return [source.id, await getSourceRuns(source.id)] as const;
        } catch {
          return [source.id, []] as const;
        }
      })
    );
    setRunsBySource(Object.fromEntries(runEntries));
  }

  useEffect(() => {
    refresh().catch(() => setSources([]));
  }, []);

  async function createSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const configText = String(form.get("config") || "{}");
    await fetch(`${API_BASE}/sources`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        name: form.get("name"),
        connector_type: form.get("connector_type"),
        url: form.get("url") || null,
        api_endpoint: form.get("api_endpoint") || null,
        frequency_minutes: Number(form.get("frequency_minutes") || 1440),
        is_active: true,
        config: JSON.parse(configText)
      })
    });
    formElement.reset();
    await refresh();
  }

  async function runSource(id: number) {
    setBusy(id);
    setRunMessage("Exécution envoyée en arrière-plan. Les volumes se mettront à jour automatiquement.");
    setRunError(null);
    try {
      const job = await launchSource(id);
      for (let attempt = 0; attempt < 450; attempt += 1) {
        await wait(2000);
        const task = await getSourceRunTaskStatus(job.task_id);
        if (attempt % 3 === 0) await refresh();
        if (task.status === "success") {
          await refresh();
          const result = task.result;
          if (result?.status === "failed") throw new Error(result.error || "Le connecteur a échoué.");
          setRunMessage(`${result?.fetched_count ?? 0} avis récupérés, ${result?.created_count ?? 0} nouveau(x) AO créé(s).`);
          return;
        }
        if (task.status === "failed") throw new Error(task.error || "La tâche de collecte a échoué.");
      }
      throw new Error("Le connecteur continue en arrière-plan. Actualisez l'activité dans quelques minutes.");
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Impossible de lancer cette source.");
      setRunMessage(null);
    } finally {
      setBusy(null);
    }
  }

  async function toggle(source: Source) {
    await fetch(`${API_BASE}/sources/${source.id}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ is_active: !source.is_active })
    });
    await refresh();
  }

  const activeCount = sources.filter((source) => source.is_active).length;
  const latestRuns = sources.map((source) => runsBySource[source.id]?.[0]).filter(Boolean);
  const failingCount = latestRuns.filter((run) => run?.status === "failed").length;
  const createdCount = latestRuns.reduce((sum, run) => sum + (run?.created_count || 0), 0);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <span className="text-sm text-foreground/60">Sources actives</span>
          <div className="mt-2 text-3xl font-semibold">{activeCount}/{sources.length}</div>
        </Card>
        <Card className="p-4">
          <span className="text-sm text-foreground/60">Derniers runs en erreur</span>
          <div className="mt-2 text-3xl font-semibold">{failingCount}</div>
        </Card>
        <Card className="p-4">
          <span className="text-sm text-foreground/60">AO créés au dernier run</span>
          <div className="mt-2 text-3xl font-semibold">{createdCount}</div>
        </Card>
        <Card className="p-4">
          <span className="text-sm text-foreground/60">Runs suivis</span>
          <div className="mt-2 text-3xl font-semibold">{latestRuns.length}</div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 className="text-sm font-semibold">Sources</h2>
          <Button onClick={refresh} variant="secondary" size="sm">
            <RefreshCw className="h-4 w-4" />
            Actualiser
          </Button>
        </div>
        {(runMessage || runError) && (
          <div className={["border-b px-4 py-3 text-sm", runError ? "border-danger/20 bg-danger-light text-danger" : "border-primary/20 bg-primary-extra-light text-primary"].join(" ")}>
            {runError || runMessage}
          </div>
        )}
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Connecteur</th>
                <th>Fonctionnement</th>
                <th>Dernier run</th>
                <th>Volumes</th>
                <th>Activité</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => {
                const latest = runsBySource[source.id]?.[0];
                const connection = connectionLabel(source);
                const canRun = source.config.connection_status !== "requires_agreement" && source.config.connection_status !== "reference_only";
                return (
                  <tr key={source.id}>
                    <td className="max-w-sm">
                      <div className="font-medium">{source.name}</div>
                      <div className="mt-1 text-xs text-foreground/60">{source.url || source.api_endpoint || "Endpoint non renseigné"}</div>
                    </td>
                    <td>
                      <div>{source.connector_type}</div>
                      <div className="mt-1 text-xs text-foreground/60">Toutes les {source.frequency_minutes} min</div>
                      <Badge tone={connection.tone}>{connection.label}</Badge>
                      {typeof source.config.blocking_reason === "string" && (
                        <div className="mt-1 max-w-xs text-xs text-foreground/60">{source.config.blocking_reason}</div>
                      )}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        {latest?.status === "failed" ? (
                          <XCircle className="h-4 w-4 text-danger" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-primary" />
                        )}
                        <Badge tone={runTone(latest?.status)}>{latest?.status || "Jamais lancé"}</Badge>
                      </div>
                      {latest?.error_message && <div className="mt-1 max-w-xs text-xs text-danger">{latest.error_message}</div>}
                    </td>
                    <td>
                      <div>{latest?.started_at ? new Date(latest.started_at).toLocaleString("fr-FR") : "Non disponible"}</div>
                      {latest && <div className="mt-1 text-xs text-foreground/60">Durée: {durationLabel(latest)}</div>}
                    </td>
                    <td>
                      <div className="font-medium">{latest?.fetched_count ?? 0} récupérés</div>
                      <div className="text-xs text-foreground/60">{latest?.created_count ?? 0} créés</div>
                    </td>
                    <td>
                      <button onClick={() => canRun && toggle(source)} disabled={!canRun} title={!canRun ? "Connexion éditeur nécessaire" : undefined}>
                        <Badge tone={source.is_active ? "green" : "neutral"}>{source.is_active ? "Actif" : "Inactif"}</Badge>
                      </button>
                    </td>
                    <td>
                      <Button onClick={() => runSource(source.id)} disabled={busy !== null || !canRun} size="sm" variant="secondary">
                        {busy === source.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                        {busy === source.id ? "En cours" : "Lancer"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {!sources.length && <tr><td colSpan={7} className="text-sm text-foreground/60">Aucune source.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold">Ajouter une source</h2>
        <form onSubmit={createSource} className="grid gap-3 lg:grid-cols-[1fr_180px_1fr_1fr_120px_1fr_auto]">
          <input name="name" placeholder="Nom" required />
          <select name="connector_type" required defaultValue="WEB_WATCH">
            <option value="BOAMP_API">BOAMP_API</option>
            <option value="TED_API">TED_API</option>
            <option value="WEB_WATCH">WEB_WATCH</option>
            <option value="RSS">RSS</option>
            <option value="EMAIL_IMPORT">EMAIL_IMPORT</option>
            <option value="MANUAL_UPLOAD">MANUAL_UPLOAD</option>
          </select>
          <input name="url" placeholder="URL" />
          <input name="api_endpoint" placeholder="Endpoint API" />
          <input name="frequency_minutes" type="number" placeholder="Fréq." />
          <input name="config" placeholder='{"keywords":["événementiel"],"days_back":30}' />
          <Button type="submit">
            <Plus className="h-4 w-4" />
            Ajouter
          </Button>
        </form>
      </Card>
    </div>
  );
}
