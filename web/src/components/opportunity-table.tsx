"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, Search, Target } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { analyzeOpportunities, updateOpportunityStatus, type OpportunityListItem } from "@/lib/api";

function tone(score: number) {
  if (score >= 80) return "green" as const;
  if (score >= 65) return "blue" as const;
  if (score >= 45) return "amber" as const;
  return "red" as const;
}

function statusLabel(status: string) {
  return (
    {
      nouveau: "À analyser",
      analyse: "Revue IA",
      a_qualifier: "À qualifier",
      pertinent: "Pertinent",
      non_pertinent: "Écarté par IA",
      go: "GO",
      watch: "WATCH",
      no_go: "NO-GO",
      archive: "Archivé"
    }[status] || status
  );
}

const QUICK_STATUSES = [
  { value: "nouveau", label: "À analyser" },
  { value: "analyse", label: "Revue IA" },
  { value: "a_qualifier", label: "À qualifier" },
  { value: "pertinent", label: "Pertinent" },
  { value: "go", label: "Étude réponse" },
  { value: "watch", label: "Surveillance" },
  { value: "non_pertinent", label: "Écarté IA" },
  { value: "no_go", label: "NO-GO" },
  { value: "archive", label: "Archivé" }
];

function decisionTone(status: string, score: number) {
  if (status === "go" || status === "pertinent" || score >= 80) return "green" as const;
  if (status === "watch" || status === "a_qualifier" || score >= 45) return "amber" as const;
  if (status === "no_go" || status === "non_pertinent") return "red" as const;
  return "blue" as const;
}

function shortReason(opportunity: OpportunityListItem, highlights: Record<string, string[]> = {}) {
  const searchHighlights = highlights[String(opportunity.id)] || highlights[opportunity.id];
  if (searchHighlights?.length) return searchHighlights.join(" ");
  if (opportunity.status === "non_pertinent" && opportunity.ai_summary) return opportunity.ai_summary;
  if (opportunity.status === "non_pertinent") return "Écarté par IA: score insuffisant ou objet hors enjeux LIVE.";
  if (opportunity.ai_summary) return opportunity.ai_summary.split("\n")[0];
  return opportunity.description || opportunity.object || "Analyse à lancer";
}

function daysUntil(value: string | null) {
  if (!value) return null;
  return Math.ceil((new Date(value).getTime() - Date.now()) / 86400000);
}

function nextAction(opportunity: OpportunityListItem) {
  const days = daysUntil(opportunity.deadline);
  if (days !== null && days < 0) return { label: "Deadline dépassée", tone: "red" as const };
  if (days !== null && days <= 3) return { label: "Traiter en urgence", tone: "red" as const };
  if (opportunity.status === "nouveau") return { label: "Analyser", tone: "blue" as const };
  if (opportunity.status === "analyse") return { label: "Décider catégorie", tone: "blue" as const };
  if (opportunity.status === "a_qualifier") return { label: "Qualifier métier", tone: "amber" as const };
  if (opportunity.status === "pertinent") return { label: "Cadrer réponse", tone: "green" as const };
  if (opportunity.status === "go") return { label: "Préparer réponse", tone: "green" as const };
  if (opportunity.status === "watch") return { label: "Surveiller", tone: "amber" as const };
  if (opportunity.status === "non_pertinent") return { label: "Hors périmètre LIVE", tone: "red" as const };
  if (opportunity.status === "no_go") return { label: "Archiver / justifier", tone: "neutral" as const };
  if (opportunity.global_score >= 65) return { label: "Qualifier GO/WATCH", tone: "green" as const };
  return { label: "Surveiller", tone: "neutral" as const };
}

export function OpportunityTable({
  canAnalyzeSelection,
  items,
  pageTitle,
  priorityCount,
  searchHighlights = {}
}: {
  canAnalyzeSelection: boolean;
  items: OpportunityListItem[];
  pageTitle: string;
  priorityCount: number;
  searchHighlights?: Record<string, string[]>;
}) {
  const router = useRouter();
  const selectableIds = useMemo(() => items.filter((item) => item.status === "nouveau").map((item) => item.id), [items]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusDrafts, setStatusDrafts] = useState<Record<number, string>>({});

  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));

  function toggleOne(id: number) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  }

  function toggleAll() {
    setSelectedIds(allSelected ? [] : selectableIds);
  }

  async function analyzeSelected() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await analyzeOpportunities(selectedIds);
      setSelectedIds([]);
      setMessage(
        `${result.analyzed_count} AO analysé(s). ${result.failed_count ? `${result.failed_count} erreur(s). ` : "Répartition IA terminée. "}Tokens: ${result.total_tokens.toLocaleString("fr-FR")}.`
      );
      router.refresh();
    } catch {
      setError("Impossible de lancer l'analyse IA sur la sélection.");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(opportunity: OpportunityListItem, nextStatus: string) {
    setStatusDrafts((current) => ({ ...current, [opportunity.id]: nextStatus }));
    setSavingId(opportunity.id);
    setMessage(null);
    setError(null);
    try {
      await updateOpportunityStatus(opportunity.id, nextStatus, "catalog_quick_select");
      setMessage(`${opportunity.title} classé en ${statusLabel(nextStatus)}.`);
      router.refresh();
    } catch {
      setStatusDrafts((current) => ({ ...current, [opportunity.id]: opportunity.status }));
      setError("Impossible d'enregistrer la décision sur cet AO.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <>
    <section className="mode-simple-only workspace-panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">{pageTitle}</h2>
          {canAnalyzeSelection && <p className="mt-1 text-xs text-foreground/50">Cochez les avis à analyser, enrichir et préparer pour le RAG.</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {canAnalyzeSelection && (
            <Button onClick={analyzeSelected} disabled={busy || !selectedIds.length} size="sm">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
              Analyser {selectedIds.length || ""}
            </Button>
          )}
          <span className="text-xs text-foreground/50">{priorityCount} priorité(s)</span>
        </div>
      </div>

      {(message || error) && (
        <div className={["mx-4 mt-4 rounded-md border px-3 py-2 text-sm", error ? "border-danger/20 bg-danger-light text-danger" : "border-primary/20 bg-primary-extra-light text-primary"].join(" ")}>
          {error || message}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-[920px]">
          <thead>
            <tr>
              {canAnalyzeSelection && (
                <th className="w-10">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Sélectionner tous les AO" />
                </th>
              )}
              <th>Appel d'offres</th>
              <th>Analyse LIVE</th>
              <th>Acheteur et échéance</th>
              <th className="w-64">Décision</th>
            </tr>
          </thead>
          <tbody>
            {items.map((opportunity) => (
              <tr key={opportunity.id}>
                {canAnalyzeSelection && (
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(opportunity.id)}
                      disabled={opportunity.status !== "nouveau" || busy}
                      onChange={() => toggleOne(opportunity.id)}
                      aria-label={`Sélectionner ${opportunity.title}`}
                    />
                  </td>
                )}
                <td className="max-w-xl">
                  <Link href={`/opportunities/${opportunity.id}`} className="font-medium text-foreground hover:text-primary hover:underline">
                    {opportunity.title}
                  </Link>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-foreground/55">{shortReason(opportunity, searchHighlights).slice(0, 240)}</p>
                  <div className="mt-2 flex gap-2 text-xs text-foreground/45">
                    <span>{opportunity.source}</span><span>·</span><span>{opportunity.source_reference || "Sans référence"}</span>
                  </div>
                </td>
                <td>
                  <div className="flex flex-col items-start gap-1.5">
                    <Badge tone={decisionTone(opportunity.status, opportunity.global_score)}>{statusLabel(opportunity.status)}</Badge>
                    <Badge tone={tone(opportunity.global_score)}>{opportunity.global_score}/100</Badge>
                  </div>
                </td>
                <td className="max-w-xs text-sm">
                  <p>{opportunity.buyer || "Acheteur non disponible"}</p>
                  <p className="mt-1 text-xs text-foreground/50">{opportunity.location || "Localisation inconnue"}</p>
                  <p className="mt-2 text-xs font-medium text-foreground/65">
                    {opportunity.deadline ? `Avant le ${new Date(opportunity.deadline).toLocaleDateString("fr-FR")}` : "Date limite inconnue"}
                  </p>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <select
                      aria-label={`Qualifier ${opportunity.title}`}
                      className="h-9 min-w-40 px-2 text-xs font-medium"
                      disabled={savingId === opportunity.id}
                      value={statusDrafts[opportunity.id] ?? opportunity.status}
                      onChange={(event) => updateStatus(opportunity, event.target.value)}
                    >
                      {QUICK_STATUSES.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
                    </select>
                    <Button asChild size="icon" variant="secondary" title="Voir le détail">
                      <Link href={`/opportunities/${opportunity.id}`}><ArrowRight className="h-4 w-4" /></Link>
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td colSpan={canAnalyzeSelection ? 5 : 4} className="py-10 text-center text-sm text-foreground/50">
                  <Search className="mr-2 inline h-4 w-4" />Aucun résultat pour cette vue.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>

    <Card className="mode-advanced-only front-panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div>
          <h2 className="text-sm font-semibold">{pageTitle}</h2>
          {canAnalyzeSelection && (
            <p className="mt-1 text-xs text-white/60">
              Sélectionnez les AO bruts. L'agent analyse l'annonce selon les enjeux LIVE, explique les écarts et propose la prochaine décision.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canAnalyzeSelection && (
            <Button onClick={analyzeSelected} disabled={busy || !selectedIds.length} size="sm" className="border-white bg-white text-brand-marine hover:bg-white/90">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
              Lancer la revue IA
            </Button>
          )}
          <div className="flex items-center gap-2 text-sm text-white/70">
            <Target className="h-4 w-4 text-brand-gold" />
            {priorityCount} opportunité(s) à prioriser
          </div>
        </div>
      </div>

      {(message || error) && (
        <div className={["mx-4 mt-4 rounded-md border px-3 py-2 text-sm", error ? "border-danger/30 bg-danger/20 text-white" : "border-white/15 bg-white/10 text-white/75"].join(" ")}>
          {error || message}
        </div>
      )}

      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              {canAnalyzeSelection && (
                <th className="w-10">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Sélectionner tous les AO" />
                </th>
              )}
              <th>AO détecté</th>
              <th>Étape & score</th>
              <th>Pourquoi détecté</th>
              <th>Acheteur / lieu</th>
              <th>Deadline</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((opportunity) => (
              <tr key={opportunity.id}>
                {canAnalyzeSelection && (
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(opportunity.id)}
                      disabled={opportunity.status !== "nouveau" || busy}
                      onChange={() => toggleOne(opportunity.id)}
                      aria-label={`Sélectionner ${opportunity.title}`}
                    />
                  </td>
                )}
                <td className="max-w-lg">
                  <div className="font-medium text-white">{opportunity.title}</div>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-white/65">
                    <span>{opportunity.source}</span>
                    <span>{opportunity.source_reference || "Référence non disponible"}</span>
                  </div>
                </td>
                <td>
                  <div className="flex flex-col gap-1">
                    <Badge tone={decisionTone(opportunity.status, opportunity.global_score)}>{statusLabel(opportunity.status)}</Badge>
                    <Badge tone={tone(opportunity.global_score)}>{opportunity.global_score}/100</Badge>
                  </div>
                </td>
                <td className="max-w-xl text-sm text-white/75">{shortReason(opportunity, searchHighlights).slice(0, 220)}</td>
                <td className="text-white/80">
                  <div>{opportunity.buyer || "Acheteur non disponible"}</div>
                  <div className="mt-1 text-xs text-white/60">{opportunity.location || "Localisation non disponible"}</div>
                </td>
                <td className="text-white/80">{opportunity.deadline ? new Date(opportunity.deadline).toLocaleDateString("fr-FR") : "Non disponible"}</td>
                <td>
                  <div className="flex min-w-56 flex-col gap-2">
                    <Badge tone={nextAction(opportunity).tone}>{nextAction(opportunity).label}</Badge>
                    <div className="flex flex-wrap items-center gap-2">
                      <select
                        aria-label={`Qualifier ${opportunity.title}`}
                        className="h-8 min-w-40 border-white/40 bg-white px-2 text-xs font-medium text-brand-marine shadow-sm"
                        disabled={savingId === opportunity.id}
                        value={statusDrafts[opportunity.id] ?? opportunity.status}
                        onChange={(event) => updateStatus(opportunity, event.target.value)}
                      >
                        {QUICK_STATUSES.map((status) => (
                          <option key={status.value} value={status.value}>
                            {status.label}
                          </option>
                        ))}
                      </select>
                      <Button asChild size="sm" variant="secondary" className="transition hover:-translate-y-0.5 hover:shadow-md">
                        <Link href={`/opportunities/${opportunity.id}`}>
                          Détail
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td colSpan={canAnalyzeSelection ? 7 : 6} className="text-sm text-white/70">
                  <Search className="mr-2 inline h-4 w-4" />
                  Aucun résultat.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
    </>
  );
}
