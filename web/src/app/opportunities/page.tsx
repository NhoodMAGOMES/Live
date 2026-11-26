import Link from "next/link";
import { CheckCircle2, ChevronLeft, ChevronRight, Cpu, Filter, Search, Sparkles, Target } from "lucide-react";

import { ImportOpportunity } from "@/components/import-opportunity";
import { OpportunityTable } from "@/components/opportunity-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getOpportunities, searchOpportunities, type OpportunityListItem, type OpportunitySearchResult } from "@/lib/api";

const PAGE_SIZE = 25;

function stringParam(value: string | string[] | undefined) {
  return typeof value === "string" ? value : "";
}

function pageHref(searchParams: Record<string, string | string[] | undefined>, page: number) {
  const params = new URLSearchParams();
  Object.entries(searchParams).forEach(([key, value]) => {
    if (typeof value === "string" && value && key !== "page") params.set(key, value);
  });
  params.set("page", String(page));
  return `/opportunities?${params.toString()}`;
}

async function load(searchParams: Record<string, string | string[] | undefined>) {
  const page = Math.max(1, Number(stringParam(searchParams.page)) || 1);
  const params = new URLSearchParams();
  for (const key of ["source", "status", "buyer", "location", "min_score", "processed", "q", "deadline", "deadline_from", "deadline_to"]) {
    const value = searchParams[key];
    if (typeof value === "string" && value) params.set(key, value);
  }
  params.set("limit", String(PAGE_SIZE));
  if (!params.has("q")) params.set("offset", String((page - 1) * PAGE_SIZE));
  try {
    if (params.get("q")) {
      const search = await searchOpportunities(`?${params}`);
      return { items: search.items, total: search.total, search, page: 1 };
    }
    return { ...(await getOpportunities(`?${params}`)), search: null as OpportunitySearchResult | null, page };
  } catch {
    return { items: [] as OpportunityListItem[], total: 0, search: null as OpportunitySearchResult | null, page };
  }
}

export default async function OpportunitiesPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const data = await load(searchParams);
  const currentStatus = typeof searchParams.status === "string" ? searchParams.status : "";
  const isProcessedView = searchParams.processed === "true";
  const searchQuery = typeof searchParams.q === "string" ? searchParams.q : "";
  const isRejectedView = currentStatus === "non_pertinent";
  const isAnalyzeView = currentStatus === "nouveau";
  const currentDeadline = typeof searchParams.deadline === "string" ? searchParams.deadline : "";
  const pageTitle = isRejectedView ? "AO écartés par IA" : isAnalyzeView ? "AO à analyser" : isProcessedView ? "Revue IA des AO" : "AO détectés";
  const pageDescription = isRejectedView
    ? "Candidats détectés sur les plateformes puis écartés par l'analyse IA car hors enjeux LIVE ou trop faibles."
    : isAnalyzeView
      ? "Vivier d'AO détectés par mots-clés, à sélectionner pour lancer l'agent d'analyse, la récupération documentaire et la préparation RAG."
      : isProcessedView
        ? "AO déjà scorés par l'IA LIVE: l'équipe peut les passer en à qualifier, pertinent, sous surveillance, écarté ou étude réponse."
        : "Tous les appels d'offres récupérés par mots-clés, avec source, score indicatif, justification, acheteur, localisation, deadline et action proposée.";
  const counts = data.items.reduce(
    (acc, opportunity) => {
      acc[opportunity.status] = (acc[opportunity.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );
  const priority = data.items.filter((opportunity) => opportunity.status === "go" || opportunity.status === "watch" || opportunity.global_score >= 65);
  const analyzed = isProcessedView ? data.total : data.items.filter((opportunity) => opportunity.status !== "nouveau").length;
  const pendingDecision = data.items.filter((opportunity) => opportunity.status === "nouveau" || opportunity.status === "analyse").length;
  const qualifiedOrRelevant = (counts.a_qualifier || 0) + (counts.pertinent || 0);
  const study = data.items.filter((opportunity) => opportunity.status === "go").length;
  const pageCount = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const tabs = [
    { label: "Tous", href: "/opportunities", active: !currentStatus && !isProcessedView },
    { label: "Nouveaux", href: "/opportunities?status=nouveau", active: isAnalyzeView },
    { label: "À décider", href: "/opportunities?processed=true", active: isProcessedView },
    { label: "Retenus", href: "/opportunities?status=pertinent", active: currentStatus === "pertinent" },
    { label: "Écartés", href: "/opportunities?status=non_pertinent", active: isRejectedView }
  ];
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mode-simple-only">
        <header className="front-panel mb-5 flex flex-wrap items-end justify-between gap-4 rounded-lg p-5 sm:p-6">
          <div>
            <p className="text-sm font-medium text-primary">Qualification des appels d'offres</p>
            <h1 className="mt-1 text-3xl font-semibold text-foreground">{pageTitle}</h1>
            <p className="mt-2 max-w-3xl text-sm text-foreground/60">{pageDescription}</p>
          </div>
          <ImportOpportunity />
        </header>

        <nav className="mb-4 flex gap-1 overflow-x-auto border-b border-border" aria-label="Vues des opportunités">
          {tabs.map((tab) => (
            <Link
              key={tab.label}
              href={tab.href}
              className={[
                "whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium",
                tab.active ? "border-primary text-primary" : "border-transparent text-foreground/55 hover:text-foreground"
              ].join(" ")}
            >
              {tab.label}
            </Link>
          ))}
        </nav>

        <section className="workspace-panel mb-4 p-4">
          <form className="flex flex-wrap items-center gap-3">
            {isProcessedView && <input type="hidden" name="processed" value="true" />}
            {currentStatus && <input type="hidden" name="status" value={currentStatus} />}
            <label className="relative min-w-[260px] flex-1">
              <span className="sr-only">Recherche IA</span>
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-foreground/35" />
              <input className="h-10 w-full pl-9" name="q" placeholder="Rechercher un objet, un acheteur, un territoire..." defaultValue={searchQuery} />
            </label>
            <Button type="submit"><Sparkles className="h-4 w-4" />Rechercher</Button>
            <details className="group w-full border-t border-border pt-3">
              <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-foreground/65">
                <Filter className="h-4 w-4" />Filtres avancés
              </summary>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <input name="source" placeholder="Source" defaultValue={stringParam(searchParams.source)} />
                <input name="buyer" placeholder="Acheteur" defaultValue={stringParam(searchParams.buyer)} />
                <input name="location" placeholder="Localisation" defaultValue={stringParam(searchParams.location)} />
                <select name="deadline" defaultValue={currentDeadline}>
                  <option value="">Toutes les échéances</option>
                  <option value="soon">Dans les 7 jours</option>
                  <option value="overdue">Dépassée</option>
                  <option value="future">À venir</option>
                  <option value="missing">Sans date</option>
                </select>
                <div className="flex gap-2">
                  <input className="min-w-0 flex-1" name="min_score" inputMode="numeric" placeholder="Score min." defaultValue={stringParam(searchParams.min_score)} />
                  <Button type="submit" variant="secondary">Appliquer</Button>
                </div>
              </div>
            </details>
          </form>
        </section>

        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm text-foreground/55">
          <span><strong className="text-foreground">{data.total.toLocaleString("fr-FR")}</strong> résultat(s)</span>
          <span className="flex items-center gap-2"><Target className="h-4 w-4 text-primary" />{priority.length} priorité(s) sur cette page</span>
        </div>
      </div>

      <div className="mode-advanced-only">
      <section className="mb-5 flex flex-wrap items-start justify-between gap-4 rounded-lg border border-white/20 bg-white/20 p-5 text-white shadow-2xl backdrop-blur-xl sm:p-6">
        <div className="max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold uppercase text-white/80">
            <Sparkles className="h-3.5 w-3.5 text-brand-gold" />
            Détection AO
          </div>
          <h1 className="text-3xl font-semibold leading-tight">{pageTitle}</h1>
          <p className="mt-2 text-sm leading-6 text-white/75">
            {pageDescription}
          </p>
        </div>
        <ImportOpportunity />
      </section>

      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-white/70">{isRejectedView ? "Écartés par IA" : isProcessedView ? "AO scorés IA" : "AO détectés"}</span>
            <Target className="h-4 w-4 text-brand-gold" />
          </div>
          <div className="mt-2 text-3xl font-semibold">{data.total}</div>
        </div>
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-white/70">{isProcessedView ? "À catégoriser" : "À analyser"}</span>
            <Cpu className="h-4 w-4 text-brand-gold" />
          </div>
          <div className="mt-2 text-3xl font-semibold">{isProcessedView ? pendingDecision : counts.nouveau || 0}</div>
        </div>
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-white/70">{isProcessedView ? "Qualifiés / pertinents" : "Revue IA"}</span>
            <CheckCircle2 className="h-4 w-4 text-brand-gold" />
          </div>
          <div className="mt-2 text-3xl font-semibold">{isProcessedView ? qualifiedOrRelevant : analyzed}</div>
        </div>
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-white/70">En étude réponse</span>
            <Sparkles className="h-4 w-4 text-brand-gold" />
          </div>
          <div className="mt-2 text-3xl font-semibold">{study}</div>
        </div>
      </div>

      <Card className="front-panel mb-4 p-4">
        <form className="grid gap-3 md:grid-cols-10">
          <label className="md:col-span-2">
            <span className="sr-only">Recherche IA</span>
            <input name="q" placeholder="Recherche IA: ex. programmation culturelle à Lille" defaultValue={searchQuery} />
          </label>
          <input name="source" placeholder="Source" defaultValue={(searchParams.source as string) || ""} />
          <select name="status" defaultValue={(searchParams.status as string) || ""}>
            <option value="">Statut</option>
            <option value="nouveau">À analyser</option>
            <option value="analyse">Revue IA à décider</option>
            <option value="a_qualifier">À qualifier</option>
            <option value="pertinent">Pertinent</option>
            <option value="non_pertinent">Écarté par IA</option>
            <option value="go">GO</option>
            <option value="watch">WATCH</option>
            <option value="no_go">NO-GO</option>
            <option value="archive">Archivé</option>
          </select>
          <input name="buyer" placeholder="Acheteur" defaultValue={(searchParams.buyer as string) || ""} />
          <input name="location" placeholder="Localisation" defaultValue={(searchParams.location as string) || ""} />
          <select name="deadline" defaultValue={currentDeadline}>
            <option value="">Deadline</option>
            <option value="soon">Proche 7 jours</option>
            <option value="overdue">Dépassée</option>
            <option value="future">Future</option>
            <option value="missing">Sans date</option>
          </select>
          <input name="min_score" placeholder="Score min." defaultValue={(searchParams.min_score as string) || ""} />
          <Button type="submit" variant="secondary">
            {searchQuery ? <Search className="h-4 w-4" /> : <Filter className="h-4 w-4" />}
            {searchQuery ? "Rechercher IA" : "Filtrer"}
          </Button>
        </form>
      </Card>
      </div>

      {data.search && (
        <div className="catalog-search-summary mb-4 rounded-md border border-white/15 bg-white/10 px-4 py-3 text-sm text-white/75 backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              Recherche IA: <strong className="text-white">{data.search.query}</strong> · {data.search.total} résultat(s) · mode {data.search.mode}
            </span>
            <span>Tokens: {data.search.total_tokens.toLocaleString("fr-FR")}</span>
          </div>
        </div>
      )}

      <OpportunityTable
        canAnalyzeSelection={isAnalyzeView}
        items={data.items}
        pageTitle={pageTitle}
        priorityCount={priority.length}
        searchHighlights={data.search?.highlights}
      />
      {!data.search && pageCount > 1 && (
        <nav className="catalog-pagination mt-4 flex items-center justify-between text-white" aria-label="Pagination des appels d'offres">
          <Button asChild variant="secondary" className={data.page <= 1 ? "pointer-events-none opacity-50" : ""}>
            <Link href={pageHref(searchParams, data.page - 1)}><ChevronLeft className="h-4 w-4" />Précédent</Link>
          </Button>
          <span className="text-sm text-white/70">Page {data.page} sur {pageCount}</span>
          <Button asChild variant="secondary" className={data.page >= pageCount ? "pointer-events-none opacity-50" : ""}>
            <Link href={pageHref(searchParams, data.page + 1)}>Suivant<ChevronRight className="h-4 w-4" /></Link>
          </Button>
        </nav>
      )}
    </div>
  );
}
