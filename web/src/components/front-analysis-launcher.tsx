"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarDays, CheckCircle2, Loader2, Play, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getFrontAnalysisStatus, runFrontAnalysis, type FrontAnalysisResult } from "@/lib/api";

function todayInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value || 0);
}

function scoreTone(score: number) {
  if (score >= 80) return "green" as const;
  if (score >= 65) return "blue" as const;
  if (score >= 45) return "amber" as const;
  return "red" as const;
}

const TERRITORY_FOCUS = {
  all: { label: "Tous territoires", departments: [] as string[] },
  north_paris: { label: "Nord + Paris", departments: ["59", "62", "75", "77", "78", "91", "92", "93", "94", "95"] },
  southwest: { label: "Bordeaux · Landes · Biarritz", departments: ["33", "40", "64"] }
};

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export function FrontAnalysisLauncher() {
  const router = useRouter();
  const [analysisDate, setAnalysisDate] = useState(todayInputValue);
  const [daysBack, setDaysBack] = useState(14);
  const [limit, setLimit] = useState(300);
  const [territoryFocus, setTerritoryFocus] = useState<keyof typeof TERRITORY_FOCUS>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FrontAnalysisResult | null>(null);

  async function launch() {
    setBusy(true);
    setError(null);
    try {
      const job = await runFrontAnalysis({
        analysis_date: analysisDate,
        days_back: daysBack,
        limit,
        min_live_score: 25,
        departments: TERRITORY_FOCUS[territoryFocus].departments
      });
      for (let attempt = 0; attempt < 300; attempt += 1) {
        await wait(2000);
        const state = await getFrontAnalysisStatus(job.task_id);
        if (state.status === "success" && state.result) {
          setResult(state.result);
          router.refresh();
          return;
        }
        if (state.status === "failed") {
          throw new Error(state.error || "La détection a échoué.");
        }
      }
      throw new Error("La détection continue en arrière-plan. Consultez les opportunités dans quelques minutes.");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Impossible de lancer l'analyse depuis le frontoffice.");
    } finally {
      setBusy(false);
    }
  }

  const counters = result
    ? [
        { label: "AO trouvés", value: result.fetched_count },
        { label: "Nouveaux à analyser", value: result.new_count },
        { label: "Déjà présents", value: result.already_known_count },
        { label: "Écartés par IA", value: result.skipped_low_score_count },
        { label: "Analysés maintenant", value: result.analyzed_count },
        { label: "Tokens", value: result.total_tokens }
      ]
    : [];

  return (
    <Card className="front-panel mb-6 p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-brand-gold" />
            <h2 className="text-sm font-semibold">1. Détecter les opportunités sur les plateformes</h2>
          </div>
          <p className="mt-1 text-sm text-white/65">Recherche plateforme par mots-clés, dédoublonnage et création du vivier d'AO à analyser.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex h-10 items-center gap-2 rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white">
            <CalendarDays className="h-4 w-4 text-brand-gold" />
            <span className="text-xs text-white/60">Jusqu'au</span>
            <input
              type="date"
              value={analysisDate}
              onChange={(event) => setAnalysisDate(event.target.value)}
              className="h-8 border-0 bg-transparent p-0 text-white"
            />
          </label>
          <select
            value={daysBack}
            onChange={(event) => setDaysBack(Number(event.target.value))}
            className="h-10 rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white"
          >
            <option value={1}>Jour seul</option>
            <option value={7}>7 jours</option>
            <option value={14}>14 jours</option>
            <option value={30}>30 jours</option>
          </select>
          <select
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
            className="h-10 rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white"
          >
            <option value={100}>100 AO</option>
            <option value={300}>300 AO</option>
            <option value={500}>500 AO</option>
          </select>
          <select
            value={territoryFocus}
            onChange={(event) => setTerritoryFocus(event.target.value as keyof typeof TERRITORY_FOCUS)}
            className="h-10 rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white"
          >
            {Object.entries(TERRITORY_FOCUS).map(([key, value]) => (
              <option key={key} value={key}>
                {value.label}
              </option>
            ))}
          </select>
          <Button onClick={launch} disabled={busy} className="border-white bg-white text-brand-marine hover:bg-white/90">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Lancer la détection
          </Button>
        </div>
      </div>

      {error && <div className="mt-4 rounded-md border border-danger/30 bg-danger/20 px-3 py-2 text-sm text-white">{error}</div>}

      {result && (
        <div className="mt-4 border-t border-white/10 pt-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            {counters.map((counter) => (
              <div key={counter.label} className="rounded-md border border-white/15 bg-white/10 p-3">
                <span className="text-xs text-white/60">{counter.label}</span>
                <div className="mt-1 text-xl font-semibold">{formatNumber(counter.value)}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-white/60">
            <span>
              Période: {result.days_back} jour(s) jusqu'au {new Date(result.analysis_date).toLocaleDateString("fr-FR")}
            </span>
            <span>Run #{result.run_id}</span>
            <span>Statut: {result.status}</span>
          </div>

          <div className="mt-4 space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <CheckCircle2 className="h-4 w-4 text-brand-gold" />
              Nouveaux AO à analyser
            </div>
            {result.new_opportunities.length ? (
              <div className="grid gap-2">
                {result.new_opportunities.slice(0, 6).map((opportunity) => (
                  <Link
                    key={opportunity.id}
                    href="/opportunities?status=nouveau"
                    className="rounded-md border border-white/15 bg-white/10 p-3 hover:bg-white/15"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="max-w-3xl">
                        <div className="text-sm font-medium text-white">{opportunity.title}</div>
                        <div className="mt-1 text-xs text-white/60">
                          {opportunity.source} · {opportunity.buyer || "Acheteur non disponible"}
                        </div>
                      </div>
                      <Badge tone={scoreTone(opportunity.global_score)}>{opportunity.global_score}/100</Badge>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="rounded-md border border-white/15 bg-white/10 p-3 text-sm text-white/65">
                Aucun nouvel AO ajouté pour cette détection.
              </div>
            )}
          </div>

          {result.rejected_candidates.length ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <XCircle className="h-4 w-4 text-brand-gold" />
                  Candidats écartés par IA
                </div>
                <Link href="/opportunities?status=non_pertinent" className="text-xs font-semibold text-white/75 hover:text-white">
                  Voir l'historique
                </Link>
              </div>
              <div className="grid gap-2">
                {result.rejected_candidates.slice(0, 5).map((candidate, index) => {
                  const content = (
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="max-w-3xl">
                        <div className="text-sm font-medium text-white">{candidate.title || "AO sans titre"}</div>
                        <div className="mt-1 text-xs text-white/60">
                          {candidate.source} · {candidate.source_reference || "Référence non disponible"} · {candidate.reason || "Score insuffisant"}
                        </div>
                      </div>
                      <Badge tone="red">{candidate.score}/100</Badge>
                    </div>
                  );
                  return candidate.opportunity_id ? (
                    <Link
                      key={`${candidate.source_reference || "candidate"}-${index}`}
                      href={`/opportunities/${candidate.opportunity_id}`}
                      className="block rounded-md border border-white/15 bg-white/10 p-3 hover:bg-white/15"
                    >
                      {content}
                    </Link>
                  ) : (
                    <div key={`${candidate.source_reference || "candidate"}-${index}`} className="rounded-md border border-white/15 bg-white/10 p-3">
                      {content}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}
