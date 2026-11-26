import Link from "next/link";
import { AlertTriangle, ArrowRight, CalendarClock, CheckCircle2, Clock3, ListChecks, Radar } from "lucide-react";

import { FrontAnalysisLauncher } from "@/components/front-analysis-launcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Dashboard, OpportunityListItem } from "@/lib/api";

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value || 0);
}

function statusLabel(status: string) {
  return ({
    nouveau: "Nouveau",
    analyse: "À décider",
    a_qualifier: "À qualifier",
    pertinent: "Retenu",
    go: "En étude",
    watch: "Surveillance",
    non_pertinent: "Écarté"
  }[status] || status);
}

function statusTone(status: string) {
  if (status === "go" || status === "pertinent") return "green" as const;
  if (status === "watch" || status === "a_qualifier") return "amber" as const;
  if (status === "non_pertinent") return "red" as const;
  return "blue" as const;
}

function daysUntil(value: string | null) {
  if (!value) return null;
  return Math.ceil((new Date(value).getTime() - Date.now()) / 86400000);
}

function deadlineLabel(value: string | null) {
  const days = daysUntil(value);
  if (days === null) return "Sans date";
  if (days < 0) return "Dépassée";
  if (days === 0) return "Aujourd'hui";
  return `J-${days}`;
}

function uniqueOpportunities(...groups: OpportunityListItem[][]) {
  const seen = new Set<number>();
  return groups.flat().filter((opportunity) => {
    if (seen.has(opportunity.id)) return false;
    seen.add(opportunity.id);
    return true;
  });
}

export function SimpleDashboard({ dashboard }: { dashboard: Dashboard | null }) {
  const statuses = dashboard?.status_counts ?? {};
  const detected = (dashboard?.total_opportunities ?? 0) + (dashboard?.rejected_opportunities ?? 0);
  const toDecide = (statuses.analyse || 0) + (statuses.a_qualifier || 0) + (statuses.pertinent || 0) + (statuses.watch || 0);
  const retained = (statuses.pertinent || 0) + (statuses.go || 0);
  const priorities = uniqueOpportunities(dashboard?.urgent_opportunities ?? [], dashboard?.latest_opportunities ?? [])
    .filter((opportunity) =>
      ["analyse", "a_qualifier", "pertinent", "go", "watch"].includes(opportunity.status) || opportunity.global_score >= 45
    )
    .slice(0, 6);
  const urgent = (dashboard?.urgent_opportunities ?? []).slice(0, 5);
  const lastRun = dashboard?.token_usage.last_run_at
    ? new Date(dashboard.token_usage.last_run_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })
    : "Aucune analyse IA";
  const metrics = [
    { label: "AO détectés", value: detected, hint: "Toutes sources", icon: Radar, href: "/opportunities" },
    { label: "À décider", value: toDecide, hint: "Revue métier attendue", icon: Clock3, href: "/opportunities?processed=true" },
    { label: "Retenus", value: retained, hint: "Pertinents ou en étude", icon: CheckCircle2, href: "/opportunities?status=pertinent" },
    { label: "Échéances proches", value: dashboard?.deadlines_soon ?? 0, hint: "Dans les 7 prochains jours", icon: CalendarClock, href: "/opportunities?deadline=soon" }
  ];
  const pipeline = [
    { label: "Détectés", count: detected, href: "/opportunities" },
    { label: "Analysés", count: dashboard?.analyzed_opportunities ?? 0, href: "/opportunities?processed=true" },
    { label: "À décider", count: toDecide, href: "/opportunities?processed=true" },
    { label: "En étude", count: dashboard?.study_opportunities ?? 0, href: "/opportunities?status=go" }
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <header className="front-panel mb-6 flex flex-wrap items-end justify-between gap-4 rounded-lg p-5 sm:p-6">
        <div>
          <p className="text-sm font-medium text-primary">Pilotage des appels d'offres</p>
          <h1 className="mt-1 text-3xl font-semibold text-foreground">Dashboard</h1>
          <p className="mt-2 text-sm text-foreground/60">Les opportunités qui demandent une action aujourd'hui.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-foreground/50 sm:inline">Dernière activité : {lastRun}</span>
          <Button asChild variant="secondary"><Link href="/opportunities"><ListChecks className="h-4 w-4" />Tous les AO</Link></Button>
        </div>
      </header>

      {!dashboard && (
        <div className="mb-5 rounded-md border border-danger/20 bg-danger-light px-4 py-3 text-sm text-danger">
          Les données sont temporairement indisponibles. Réessayez dans quelques instants.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Link key={metric.label} href={metric.href} className="workspace-panel flex min-h-28 items-start justify-between p-4 transition hover:border-primary/30 hover:shadow-md">
              <div>
                <p className="text-sm text-foreground/60">{metric.label}</p>
                <p className="mt-2 text-3xl font-semibold text-foreground">{formatNumber(metric.value)}</p>
                <p className="mt-2 text-xs text-foreground/50">{metric.hint}</p>
              </div>
              <Icon className="h-5 w-5 text-primary" />
            </Link>
          );
        })}
      </div>

      <section className="workspace-panel mt-5 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Pipeline décisionnel</h2>
          <span className="text-xs text-foreground/50">{formatNumber(dashboard?.active_sources ?? 0)} sources actives</span>
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {pipeline.map((step, index) => (
            <Link key={step.label} href={step.href} className="group flex items-center gap-3 rounded-md border border-border bg-muted/55 p-3 hover:border-primary/30">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold text-primary">{index + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="text-xs text-foreground/55">{step.label}</p>
                <p className="text-lg font-semibold">{formatNumber(step.count)}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-foreground/30 group-hover:text-primary" />
            </Link>
          ))}
        </div>
      </section>

      <div className="mt-5"><FrontAnalysisLauncher /></div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.6fr_1fr]">
        <section className="workspace-panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div><h2 className="font-semibold">Opportunités prioritaires</h2><p className="mt-1 text-xs text-foreground/50">Score, échéance et décision à prendre.</p></div>
            <Link href="/opportunities?processed=true" className="text-sm font-semibold text-primary hover:underline">Voir tout</Link>
          </div>
          <div className="divide-y divide-border">
            {priorities.map((opportunity) => (
              <Link key={opportunity.id} href={`/opportunities/${opportunity.id}`} className="grid gap-3 px-5 py-4 hover:bg-muted/45 sm:grid-cols-[1fr_auto_auto] sm:items-center">
                <div className="min-w-0"><p className="truncate text-sm font-medium">{opportunity.title}</p><p className="mt-1 truncate text-xs text-foreground/50">{opportunity.buyer || opportunity.source}</p></div>
                <Badge tone={statusTone(opportunity.status)}>{statusLabel(opportunity.status)}</Badge>
                <div className="flex items-center justify-between gap-3 sm:justify-end"><span className="text-sm font-semibold text-brand-marine">{opportunity.global_score}/100</span><ArrowRight className="h-4 w-4 text-foreground/35" /></div>
              </Link>
            ))}
            {!priorities.length && <p className="px-5 py-8 text-center text-sm text-foreground/50">Aucune opportunité prioritaire.</p>}
          </div>
        </section>

        <section className="workspace-panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div><h2 className="font-semibold">Échéances</h2><p className="mt-1 text-xs text-foreground/50">Les prochaines dates à sécuriser.</p></div>
            <CalendarClock className="h-5 w-5 text-primary" />
          </div>
          <div className="divide-y divide-border">
            {urgent.map((opportunity) => (
              <Link key={opportunity.id} href={`/opportunities/${opportunity.id}`} className="flex items-center justify-between gap-3 px-5 py-4 hover:bg-muted/45">
                <div className="min-w-0"><p className="truncate text-sm font-medium">{opportunity.title}</p><p className="mt-1 text-xs text-foreground/50">{opportunity.deadline ? new Date(opportunity.deadline).toLocaleDateString("fr-FR") : "Date inconnue"}</p></div>
                <Badge tone={(daysUntil(opportunity.deadline) ?? 99) <= 3 ? "red" : "amber"}>{deadlineLabel(opportunity.deadline)}</Badge>
              </Link>
            ))}
            {!urgent.length && <div className="flex items-center gap-2 px-5 py-8 text-sm text-foreground/50"><AlertTriangle className="h-4 w-4" />Aucune échéance proche.</div>}
          </div>
          <div className="border-t border-border bg-muted/35 px-5 py-3 text-xs text-foreground/50">
            Usage IA : {formatNumber(dashboard?.token_usage.total_tokens ?? 0)} tokens
          </div>
        </section>
      </div>
    </div>
  );
}
