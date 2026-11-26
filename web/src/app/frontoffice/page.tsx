import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Clock,
  Cpu,
  ListChecks,
  Sparkles,
  Target
} from "lucide-react";

import { AoFranceMap } from "@/components/ao-france-map";
import { FrontAnalysisLauncher } from "@/components/front-analysis-launcher";
import { SimpleDashboard } from "@/components/simple-dashboard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getDashboard, type Dashboard, type OpportunityListItem } from "@/lib/api";

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value || 0);
}

function scoreTone(score: number) {
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

function daysUntil(value: string | null) {
  if (!value) return null;
  return Math.ceil((new Date(value).getTime() - Date.now()) / 86400000);
}

function deadlineLabel(value: string | null) {
  const days = daysUntil(value);
  if (days === null) return "Deadline inconnue";
  if (days < 0) return "Échéance dépassée";
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return "Demain";
  return `J-${days}`;
}

function nextAction(opportunity: OpportunityListItem) {
  const days = daysUntil(opportunity.deadline);
  if (days !== null && days < 0) return { label: "Rattrapage / clôture", tone: "red" as const };
  if (days !== null && days <= 3) return { label: "Décision immédiate", tone: "red" as const };
  if (opportunity.status === "nouveau") return { label: "Analyse IA", tone: "blue" as const };
  if (opportunity.status === "go") return { label: "Étude réponse", tone: "green" as const };
  if (opportunity.status === "watch") return { label: "Revue métier", tone: "amber" as const };
  if (opportunity.global_score >= 65) return { label: "Qualifier", tone: "green" as const };
  return { label: "Surveiller", tone: "neutral" as const };
}

function uniqueOpportunities(...groups: OpportunityListItem[][]) {
  const seen = new Set<number>();
  return groups.flat().filter((opportunity) => {
    if (seen.has(opportunity.id)) return false;
    seen.add(opportunity.id);
    return true;
  });
}

async function loadDashboard(): Promise<Dashboard | null> {
  try {
    return await getDashboard();
  } catch {
    return null;
  }
}

export default async function FrontofficePage() {
  const dashboard = await loadDashboard();
  const statusCounts = dashboard?.status_counts ?? {};
  const tokenUsage = dashboard?.token_usage ?? {
    total_tokens: 0,
    input_tokens: 0,
    output_tokens: 0,
    run_count: 0,
    orchestration_run_count: 0,
    orchestrated_tokens: 0,
    success_count: 0,
    failure_count: 0,
    last_run_at: null,
    last_model: null
  };
  const rejected = dashboard?.rejected_opportunities ?? 0;
  const analyzed = dashboard?.analyzed_opportunities ?? (statusCounts.analyse || 0);
  const relevant = dashboard?.relevant_opportunities ?? (dashboard?.high_relevance || 0);
  const study = dashboard?.study_opportunities ?? (statusCounts.go || 0);
  const total = dashboard?.total_opportunities ?? 0;
  const pipelineTotal = total + rejected;
  const successRate = tokenUsage.run_count ? Math.round((tokenUsage.success_count / tokenUsage.run_count) * 100) : 0;
  const priorityQueue = uniqueOpportunities(dashboard?.urgent_opportunities ?? [], dashboard?.latest_opportunities ?? [])
    .filter((opportunity) => ["nouveau", "analyse", "a_qualifier", "pertinent", "go", "watch"].includes(opportunity.status))
    .slice(0, 6);
  const pipeline = [
    {
      key: "nouveau",
      label: "À analyser",
      count: dashboard?.to_analyze ?? 0,
      href: "/opportunities?status=nouveau",
      description: "File d'attente brute: AO trouvés par mots-clés, pas encore scorés par l'IA LIVE.",
      next: "Sélectionner puis lancer l'analyse IA."
    },
    {
      key: "analyse",
      label: "Revue IA",
      count: analyzed,
      href: "/opportunities?processed=true",
      description: "Dossiers déjà scorés: l'IA explique l'intérêt LIVE, les risques et l'orientation proposée.",
      next: "Relire puis décider: qualifier, pertinent, surveillance ou écart."
    },
    {
      key: "a_qualifier",
      label: "À qualifier",
      count: statusCounts.a_qualifier ?? 0,
      href: "/opportunities?status=a_qualifier",
      description: "Zone de doute métier: signal intéressant mais pièces, budget, deadline ou capacité à confirmer.",
      next: "Trancher en pertinent, surveillance ou écarté."
    },
    {
      key: "pertinent",
      label: "Pertinents",
      count: statusCounts.pertinent ?? 0,
      href: "/opportunities?status=pertinent",
      description: "Signal LIVE favorable: enjeu compatible avec programmation, lieu vivant, exploitation ou revenus.",
      next: "Préparer le passage en étude réponse."
    },
    {
      key: "go",
      label: "En étude réponse",
      count: study,
      href: "/opportunities?status=go",
      description: "GO métier: approfondir l'offre, le budget, les partenaires, la note technique et le planning.",
      next: "Construire le positionnement de réponse."
    },
    {
      key: "watch",
      label: "Sous surveillance",
      count: statusCounts.watch ?? 0,
      href: "/opportunities?status=watch",
      description: "Signal faible ou incomplet mais pas à perdre: attendre pièces, contexte ou arbitrage territoire.",
      next: "Revoir plus tard ou reclasser."
    },
    {
      key: "non_pertinent",
      label: "Écartés",
      count: rejected,
      href: "/opportunities?status=non_pertinent",
      description: "Hors enjeux LIVE, score insuffisant ou refus métier; la justification IA/humaine reste visible.",
      next: "Conserver la trace et éviter les faux positifs."
    }
  ];
  const stats = [
    { label: "AO détectés", value: formatNumber(total), hint: "AO récupérés toutes sources", icon: ListChecks },
    { label: "Écartés par IA", value: formatNumber(rejected), hint: "Candidats détectés puis exclus de la liste métier", icon: AlertTriangle },
    { label: "Revue IA", value: formatNumber(analyzed), hint: "Rapport ou scoring disponible", icon: Cpu },
    { label: "Signaux favorables", value: formatNumber(relevant), hint: "Score ou statut métier exploitable", icon: CheckCircle2 },
    { label: "En étude réponse", value: formatNumber(study), hint: "GO prêts à cadrer", icon: Target },
    { label: "Deadlines proches", value: formatNumber(dashboard?.deadlines_soon ?? 0), hint: "Transversal: peut recouper Revue IA, À qualifier ou GO", icon: CalendarClock },
    { label: "Tokens IA directs", value: formatNumber(tokenUsage.total_tokens), hint: `${formatNumber(tokenUsage.run_count)} runs directs`, icon: Activity }
  ];
  const workflow = [
    {
      label: "Recherche plateformes",
      description: "Mots-clés LIVE sur BOAMP et sources publiques, puis dédoublonnage du vivier.",
      icon: ListChecks
    },
    {
      label: "Analyse IA LIVE",
      description: "Scoring stratégie LIVE, rapport, risques, raisons d'écarter ou de poursuivre.",
      icon: Cpu
    },
    {
      label: "Décision métier",
      description: "L'équipe LIVE classe en à qualifier, pertinent, surveillance, écarté ou GO.",
      icon: Target
    },
    {
      label: "Étude réponse",
      description: "Approfondissement concurrence, budget, note technique, planning et partenaires.",
      icon: CalendarClock
    }
  ];

  return (
    <>
      <div className="mode-simple-only">
        <SimpleDashboard dashboard={dashboard} />
      </div>
      <div className="mode-advanced-only mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <section className="front-panel mb-6 overflow-hidden rounded-lg p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold uppercase text-white/80">
              <Sparkles className="h-3.5 w-3.5 text-brand-gold" />
              Dashboard métier
            </div>
            <h1 className="max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
              Détecter, noter et décider les AO LIVE.
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-white/75">
              Un parcours unique: récupérer les opportunités sur les plateformes, laisser l'IA les scorer selon les enjeux LIVE, puis décider les dossiers à suivre ou à passer en étude réponse.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <AoFranceMap points={dashboard?.map_points ?? []} total={total} />
            <Button asChild className="rounded-full border-white bg-white px-4 text-brand-marine hover:bg-white/90">
              <Link href="/opportunities">
                <ListChecks className="h-4 w-4" />
                Ouvrir les AO détectés
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <Card className="front-panel mb-5 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Filtres rapides</h2>
            <p className="mt-1 text-xs text-white/60">Ouvrir directement la liste AO selon une étape, une zone ou une échéance.</p>
          </div>
          <Badge tone="blue">Dashboard vers catalogue</Badge>
        </div>
        <form action="/opportunities" className="grid gap-3 md:grid-cols-5">
          <select name="status" defaultValue="">
            <option value="">Tous les statuts</option>
            <option value="nouveau">À analyser</option>
            <option value="analyse">Revue IA</option>
            <option value="a_qualifier">À qualifier</option>
            <option value="pertinent">Pertinent</option>
            <option value="go">Étude réponse</option>
            <option value="watch">Sous surveillance</option>
            <option value="non_pertinent">Écartés IA</option>
          </select>
          <select name="location" defaultValue="">
            <option value="">Toutes les zones</option>
            <option value="Nord">Nord</option>
            <option value="Paris">Paris</option>
            <option value="Bordeaux">Bordeaux</option>
            <option value="Landes">Landes</option>
            <option value="Biarritz">Biarritz</option>
          </select>
          <select name="deadline" defaultValue="">
            <option value="">Toutes deadlines</option>
            <option value="soon">Proches 7 jours</option>
            <option value="overdue">Dépassées</option>
            <option value="future">Futures</option>
            <option value="missing">Sans date</option>
          </select>
          <input name="min_score" placeholder="Score min." />
          <Button type="submit" variant="secondary">
            <ListChecks className="h-4 w-4" />
            Voir les AO
          </Button>
        </form>
      </Card>

      {!dashboard && (
        <Card className="mb-5 border-brand-gold/60 bg-brand-gold/15 p-4 text-sm text-brand-marine">
          API indisponible. Lancez `make dev`, puis `make migrate` et `make seed`.
        </Card>
      )}

      <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {workflow.map((step, index) => {
          const Icon = step.icon;
          return (
            <div key={step.label} className="front-panel rounded-md p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-xs font-semibold text-brand-marine">{index + 1}</span>
                  <span className="text-sm font-semibold text-white">{step.label}</span>
                </div>
                <Icon className="h-4 w-4 text-brand-gold" />
              </div>
              <p className="mt-3 text-xs leading-5 text-white/65">{step.description}</p>
            </div>
          );
        })}
      </div>

      <FrontAnalysisLauncher />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="front-panel rounded-md p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <span className="text-sm text-white/70">{stat.label}</span>
                  <div className="mt-2 text-3xl font-semibold">{stat.value}</div>
                </div>
                <Icon className="h-5 w-5 text-brand-gold" />
              </div>
              <p className="mt-3 text-xs leading-5 text-white/60">{stat.hint}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 space-y-4">
        <section className="front-panel rounded-md p-4">
          <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold">2. Tunnel de décision AO LIVE</h2>
              <Badge tone="blue">{formatNumber(pipelineTotal)} AO suivis</Badge>
            </div>
          <p className="mt-2 text-sm leading-6 text-white/65">
            Le flux part d'une recherche par mots-clés, passe par une revue IA, puis l'équipe LIVE tranche progressivement: qualifier, rendre pertinent, surveiller, écarter ou lancer l'étude de réponse.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {pipeline.map((step) => (
              <Link key={step.key} href={step.href} className="rounded-md border border-white/15 bg-white/10 p-4 transition hover:bg-white/15">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div>
                    <span className="text-sm font-semibold text-white">{step.label}</span>
                    <p className="mt-1 min-h-10 text-xs leading-5 text-white/62">{step.description}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-brand-gold" />
                </div>
                <p className="mb-3 rounded-md border border-white/10 bg-white/10 px-2 py-1.5 text-xs leading-5 text-white/70">{step.next}</p>
                <div className="mb-2 flex items-end justify-between gap-3">
                  <span className="text-3xl font-semibold">{formatNumber(step.count)}</span>
                  <span className="text-xs uppercase text-white/50">AO</span>
                </div>
                <div className="h-2 rounded-sm bg-white/20">
                  <div className="h-2 rounded-sm bg-brand-gold" style={{ width: `${Math.min(100, (step.count / Math.max(1, pipelineTotal)) * 100)}%` }} />
                </div>
              </Link>
            ))}
          </div>
          <div className="mt-5 grid gap-3 border-t border-white/10 pt-4 text-sm text-white/70 md:grid-cols-2">
            <div className="flex items-center justify-between gap-3">
              <span>Sources actives</span>
              <span className="font-medium text-white">{formatNumber(dashboard?.active_sources ?? 0)}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Taux succès agents</span>
              <span className="font-medium text-white">{successRate}%</span>
            </div>
          </div>
        </section>

        <section className="front-panel rounded-md p-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold">Activité IA et consommation agents</h2>
              <p className="mt-1 text-sm text-white/65">Suivi des tokens directs consommés par l'analyse et la recherche IA, hors totaux recopiés par les cycles d'orchestration.</p>
            </div>
            <Badge tone={tokenUsage.failure_count ? "amber" : "green"}>
              {formatNumber(tokenUsage.success_count)} succès / {formatNumber(tokenUsage.failure_count)} échec(s)
            </Badge>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <div className="rounded-md border border-white/15 bg-white/10 p-3">
              <span className="text-xs text-white/60">Tokens directs</span>
              <div className="mt-1 text-2xl font-semibold">{formatNumber(tokenUsage.total_tokens)}</div>
            </div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3">
              <span className="text-xs text-white/60">Entrée</span>
              <div className="mt-1 text-2xl font-semibold">{formatNumber(tokenUsage.input_tokens)}</div>
            </div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3">
              <span className="text-xs text-white/60">Sortie</span>
              <div className="mt-1 text-2xl font-semibold">{formatNumber(tokenUsage.output_tokens)}</div>
            </div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3">
              <span className="text-xs text-white/60">Dernier modèle</span>
              <div className="mt-1 truncate text-sm font-semibold">{tokenUsage.last_model || "Non disponible"}</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-white/60">
            <span>{formatNumber(tokenUsage.run_count)} runs directs enregistrés</span>
            {tokenUsage.orchestration_run_count ? (
              <span>{formatNumber(tokenUsage.orchestration_run_count)} cycle(s) orchestration exclus</span>
            ) : null}
            {tokenUsage.orchestrated_tokens ? (
              <span>{formatNumber(tokenUsage.orchestrated_tokens)} tokens orchestrés non additionnés</span>
            ) : null}
            <span>Dernière activité: {tokenUsage.last_run_at ? new Date(tokenUsage.last_run_at).toLocaleString("fr-FR") : "Non disponible"}</span>
          </div>
        </section>
      </div>

      <div className="mt-6 space-y-4">
        <Card className="front-panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-border p-4">
            <div>
              <h2 className="text-sm font-semibold">3. Décider les opportunités prioritaires</h2>
              <p className="mt-1 text-xs text-white/60">Score LIVE, statut, deadline et prochaine action métier.</p>
            </div>
            <Link href="/opportunities" className="text-sm font-medium text-white">
              Voir tout
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>AO</th>
                  <th>Score</th>
                  <th>Statut</th>
                  <th>Deadline</th>
                  <th>Action</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {priorityQueue.map((opportunity) => (
                  <tr key={opportunity.id}>
                    <td className="max-w-md">
                      <div className="font-medium text-white">{opportunity.title}</div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-white/60">
                        <span>{opportunity.source}</span>
                        <span>{opportunity.buyer || "Acheteur non disponible"}</span>
                      </div>
                    </td>
                    <td>
                      <Badge tone={scoreTone(opportunity.global_score)}>{opportunity.global_score}/100</Badge>
                    </td>
                    <td>{statusLabel(opportunity.status)}</td>
                    <td>
                      <Badge tone={daysUntil(opportunity.deadline) !== null && Number(daysUntil(opportunity.deadline)) <= 3 ? "red" : "amber"}>
                        {deadlineLabel(opportunity.deadline)}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={nextAction(opportunity).tone}>{nextAction(opportunity).label}</Badge>
                    </td>
                    <td>
                      <Button asChild size="icon" variant="ghost" title="Ouvrir">
                        <Link href={`/opportunities/${opportunity.id}`}>
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </td>
                  </tr>
                ))}
                {!priorityQueue.length && (
                  <tr>
                    <td colSpan={6} className="text-sm text-white/70">
                      Aucun AO prioritaire pour le moment.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        <section className="front-panel rounded-md p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-brand-gold" />
              <h2 className="text-sm font-semibold">4. Suivre les réponses et deadlines</h2>
            </div>
            <Badge tone="amber">{formatNumber((dashboard?.urgent_opportunities ?? []).length)} échéance(s)</Badge>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {(dashboard?.urgent_opportunities ?? []).slice(0, 5).map((opportunity) => (
              <Link key={opportunity.id} href={`/opportunities/${opportunity.id}`} className="block rounded-md border border-white/15 bg-white/10 p-3 hover:bg-white/15">
                <div className="flex items-center justify-between gap-3">
                  <span className="line-clamp-2 text-sm font-medium">{opportunity.title}</span>
                  <Badge tone={daysUntil(opportunity.deadline) !== null && Number(daysUntil(opportunity.deadline)) <= 3 ? "red" : "amber"}>
                    {deadlineLabel(opportunity.deadline)}
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-white/60">
                  {opportunity.deadline ? new Date(opportunity.deadline).toLocaleDateString("fr-FR") : "Date non disponible"} · {opportunity.buyer || "Acheteur non disponible"}
                </p>
              </Link>
            ))}
            {!(dashboard?.urgent_opportunities ?? []).length && (
              <div className="rounded-md border border-white/15 bg-white/10 p-3 text-sm text-white/65">
                Aucune deadline future détectée.
              </div>
            )}
          </div>
          <div className="mt-4 flex items-center gap-2 border-t border-white/10 pt-4 text-xs text-white/60">
            <Clock className="h-4 w-4 text-brand-gold" />
            Les deadlines proches doivent être revues avant qualification GO/WATCH.
          </div>
        </section>
      </div>
      </div>
    </>
  );
}
