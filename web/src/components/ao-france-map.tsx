"use client";

import Link from "next/link";
import { ArrowRight, Loader2, MapPinned, RotateCcw, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDashboardMap, type DashboardMapPoint } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "", label: "Tous statuts" },
  { value: "nouveau", label: "À analyser" },
  { value: "analyse", label: "Revue IA" },
  { value: "a_qualifier", label: "À qualifier" },
  { value: "pertinent", label: "Pertinent" },
  { value: "non_pertinent", label: "Écarté" },
  { value: "go", label: "GO" },
  { value: "watch", label: "WATCH" },
  { value: "no_go", label: "NO-GO" }
];

const DEADLINE_OPTIONS = [
  { value: "", label: "Toutes deadlines" },
  { value: "soon", label: "Proche 7 jours" },
  { value: "overdue", label: "Dépassée" },
  { value: "future", label: "Future" },
  { value: "missing", label: "Sans date" }
];

const SCORE_OPTIONS = [
  { value: "", label: "Tous scores" },
  { value: "high", label: "Score 65+" },
  { value: "medium", label: "Score 45-64" },
  { value: "low", label: "Score < 45" }
];

const TERRITORY_OPTIONS = [
  { value: "", label: "Tous territoires" },
  { value: "metropole", label: "Métropole" },
  { value: "overseas", label: "Outre-mer" },
  { value: "unmapped", label: "Non cartographié" }
];

const DEFAULT_FILTERS = {
  query: "",
  zone: "",
  status: "",
  deadline: "",
  score: "",
  territory: ""
};

type MapFilters = typeof DEFAULT_FILTERS;

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-FR").format(value || 0);
}

function normalize(value: string | null | undefined) {
  return (value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function statusLabel(status: string) {
  return STATUS_OPTIONS.find((option) => option.value === status)?.label || status;
}

function scoreTone(score: number) {
  if (score >= 80) return "green" as const;
  if (score >= 45) return "amber" as const;
  return "red" as const;
}

function pinRadius(count: number, maxCount: number) {
  if (!maxCount) return 2.4;
  return Math.max(2.4, Math.min(7.2, 2.4 + Math.sqrt(count / maxCount) * 5.2));
}

function countForPoint(point: DashboardMapPoint, filters: MapFilters) {
  const statusCount = filters.status ? point.status_counts[filters.status] ?? 0 : point.count;
  const deadlineCount = filters.deadline ? point.deadline_counts?.[filters.deadline] ?? 0 : point.count;
  return Math.min(statusCount, deadlineCount);
}

function scoreMatches(score: number, filter: string) {
  if (!filter) return true;
  if (filter === "high") return score >= 65;
  if (filter === "medium") return score >= 45 && score < 65;
  if (filter === "low") return score < 45;
  return true;
}

function territoryMatches(point: DashboardMapPoint, filter: string) {
  if (!filter) return true;
  const mapped = point.x !== null && point.y !== null && !point.is_overseas;
  if (filter === "metropole") return mapped;
  if (filter === "overseas") return point.is_overseas;
  if (filter === "unmapped") return !point.is_overseas && (point.x === null || point.y === null);
  return true;
}

function queryMatches(point: DashboardMapPoint, query: string) {
  const cleanQuery = normalize(query);
  if (!cleanQuery) return true;
  const opportunityText = point.opportunities.map((opportunity) => [opportunity.title, opportunity.buyer, opportunity.status].join(" ")).join(" ");
  const haystack = normalize([point.label, point.department_name, point.department_code, point.search_text, opportunityText].join(" "));
  return haystack.includes(cleanQuery);
}

function zoneHref(point: DashboardMapPoint, filters: MapFilters) {
  const params = new URLSearchParams();
  params.set("location", point.department_code || point.department_name);
  if (filters.status) params.set("status", filters.status);
  if (filters.deadline) params.set("deadline", filters.deadline);
  if (filters.query) params.set("q", filters.query);
  if (filters.score === "high") params.set("min_score", "65");
  if (filters.score === "medium") params.set("min_score", "45");
  return `/opportunities?${params.toString()}`;
}

export function AoFranceMap({ points: initialPoints, total }: { points: DashboardMapPoint[]; total: number }) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [points, setPoints] = useState(initialPoints);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [filters, setFilters] = useState<MapFilters>(DEFAULT_FILTERS);
  const hasFilters = Object.values(filters).some(Boolean);
  const zoneOptions = useMemo(() => [...points].sort((a, b) => a.label.localeCompare(b.label, "fr")), [points]);
  const filteredPoints = useMemo(
    () =>
      points.filter((point) => {
        if (filters.zone && point.key !== filters.zone) return false;
        if (!territoryMatches(point, filters.territory)) return false;
        if (!scoreMatches(point.highest_score, filters.score)) return false;
        if (!queryMatches(point, filters.query)) return false;
        return countForPoint(point, filters) > 0;
      }),
    [filters, points]
  );
  const mappedPoints = useMemo(() => filteredPoints.filter((point) => point.x !== null && point.y !== null && !point.is_overseas), [filteredPoints]);
  const sidePoints = useMemo(() => filteredPoints.filter((point) => point.x === null || point.y === null || point.is_overseas), [filteredPoints]);
  const sortedPoints = useMemo(() => [...filteredPoints].sort((a, b) => countForPoint(b, filters) - countForPoint(a, filters)), [filteredPoints, filters]);
  const maxCount = Math.max(1, ...mappedPoints.map((point) => countForPoint(point, filters)));
  const activePoint = filteredPoints.find((point) => point.key === activeKey) || sortedPoints[0] || null;
  const mappedCount = mappedPoints.reduce((sum, point) => sum + countForPoint(point, filters), 0);
  const filteredTotal = filteredPoints.reduce((sum, point) => sum + countForPoint(point, filters), 0);
  const activeOpportunities = useMemo(() => {
    if (!activePoint) return [];
    return activePoint.opportunities.filter((opportunity) => {
      if (filters.status && opportunity.status !== filters.status) return false;
      if (filters.query) {
        const haystack = normalize([opportunity.title, opportunity.buyer, opportunity.status].join(" "));
        if (!haystack.includes(normalize(filters.query))) return false;
      }
      return true;
    });
  }, [activePoint, filters.query, filters.status]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (activeKey && filteredPoints.some((point) => point.key === activeKey)) return;
    setActiveKey(sortedPoints[0]?.key || null);
  }, [activeKey, filteredPoints, open, sortedPoints]);

  async function openMap() {
    setActiveKey((current) => current || sortedPoints[0]?.key || null);
    setOpen(true);
    if (points.length || loading) return;
    setLoading(true);
    setLoadError(false);
    try {
      setPoints(await getDashboardMap());
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  function updateFilter<Key extends keyof MapFilters>(key: Key, value: MapFilters[Key]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  const modal = open ? (
    <div className="fixed inset-0 z-[100] bg-brand-marine/85 p-2 text-white backdrop-blur-md sm:p-4">
      <button aria-label="Fermer la carte" className="absolute inset-0 h-full w-full cursor-default" onClick={() => setOpen(false)} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Carte France des AO détectés"
        className="relative mx-auto flex h-[calc(100dvh-1rem)] w-full max-w-[96rem] flex-col overflow-hidden rounded-lg border border-white/20 bg-brand-marine shadow-2xl sm:h-[calc(100dvh-2rem)]"
      >
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/15 px-4 py-4 sm:px-5">
          <div>
            <div className="flex items-center gap-2">
              <MapPinned className="h-5 w-5 text-brand-gold" />
              <h2 className="text-lg font-semibold">Carte France des AO détectés</h2>
            </div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-white/65">
              <span>{formatNumber(total)} AO visibles</span>
              <span>{formatNumber(filteredTotal)} AO dans le filtre</span>
              <span>{formatNumber(mappedCount)} positions territoriales</span>
              <span>{formatNumber(mappedPoints.length)} pins métropole</span>
            </div>
          </div>
          <Button type="button" size="icon" variant="ghost" className="text-white hover:bg-white/10 hover:text-white" onClick={() => setOpen(false)} title="Fermer">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="border-b border-white/15 bg-white/5 px-4 py-3 sm:px-5">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-white/65">
            <SlidersHorizontal className="h-3.5 w-3.5 text-brand-gold" />
            Filtres carte
          </div>
          <div className="grid gap-2 md:grid-cols-[minmax(11rem,1.5fr)_repeat(5,minmax(9rem,1fr))_auto]">
            <input
              value={filters.query}
              onChange={(event) => updateFilter("query", event.target.value)}
              placeholder="AO, acheteur, ville..."
              className="h-10 rounded-md border border-white/20 bg-white px-3 text-sm text-brand-marine placeholder:text-brand-marine/50"
            />
            <select
              value={filters.zone}
              onChange={(event) => updateFilter("zone", event.target.value)}
              className="h-10 rounded-md border border-white/20 bg-white px-3 text-sm text-brand-marine"
            >
              <option value="">Toutes zones</option>
              {zoneOptions.map((point) => (
                <option key={point.key} value={point.key}>
                  {point.label}
                </option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
              className="h-10 rounded-md border border-white/20 bg-white px-3 text-sm text-brand-marine"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={filters.deadline}
              onChange={(event) => updateFilter("deadline", event.target.value)}
              className="h-10 rounded-md border border-white/20 bg-white px-3 text-sm text-brand-marine"
            >
              {DEADLINE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={filters.score}
              onChange={(event) => updateFilter("score", event.target.value)}
              className="h-10 rounded-md border border-white/20 bg-white px-3 text-sm text-brand-marine"
            >
              {SCORE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={filters.territory}
              onChange={(event) => updateFilter("territory", event.target.value)}
              className="h-10 rounded-md border border-white/20 bg-white px-3 text-sm text-brand-marine"
            >
              {TERRITORY_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <Button type="button" variant="secondary" className="h-10 whitespace-nowrap" onClick={() => setFilters(DEFAULT_FILTERS)} disabled={!hasFilters}>
              <RotateCcw className="h-4 w-4" />
              Reset
            </Button>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 overflow-hidden lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="flex min-h-0 flex-col p-3 sm:p-5">
            <div className="relative min-h-[24rem] flex-1 overflow-hidden">
              {mappedPoints.length ? (
                <svg viewBox="0 0 100 100" className="h-full min-h-[24rem] w-full" role="img" aria-label="Carte stylisée de la France">
                  <path
                    d="M34 9 L54 7 L69 14 L79 24 L92 30 L88 43 L93 55 L82 66 L81 76 L71 77 L64 86 L54 83 L45 89 L36 80 L25 82 L17 72 L20 61 L12 55 L17 45 L10 35 L22 29 L25 18 Z"
                    className="fill-white/10 stroke-white/35"
                    strokeWidth="0.9"
                  />
                  <path d="M78 84 C82 86 82 92 78 95 C74 92 74 86 78 84 Z" className="fill-white/10 stroke-white/35" strokeWidth="0.8" />
                  <path d="M12 35 L25 37 M20 61 L31 61 M36 80 L42 70 M54 7 L53 21 M69 14 L64 30 M82 66 L70 61" className="stroke-white/10" strokeWidth="0.5" />
                  {mappedPoints.map((point) => {
                    const selected = activePoint?.key === point.key;
                    const displayedCount = countForPoint(point, filters);
                    const radius = pinRadius(displayedCount, maxCount);
                    return (
                      <g
                        key={point.key}
                        tabIndex={0}
                        role="button"
                        aria-label={`${point.label}, ${displayedCount} AO`}
                        transform={`translate(${point.x} ${point.y})`}
                        className="cursor-pointer outline-none"
                        onClick={() => setActiveKey(point.key)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") setActiveKey(point.key);
                        }}
                      >
                        <title>{`${point.label} - ${displayedCount} AO`}</title>
                        <circle r={radius + 1.2} className={selected ? "fill-brand-gold/35" : "fill-brand-blue/25"} />
                        <circle r={radius} className={selected ? "fill-brand-gold stroke-white" : "fill-brand-blue stroke-white/80"} strokeWidth="0.65" />
                        {displayedCount > 1 ? (
                          <text textAnchor="middle" dominantBaseline="middle" className="pointer-events-none fill-white text-[3px] font-semibold">
                            {displayedCount > 99 ? "99+" : displayedCount}
                          </text>
                        ) : null}
                      </g>
                    );
                  })}
                </svg>
              ) : (
                <div className="flex h-full min-h-[24rem] items-center justify-center rounded-md border border-white/15 bg-white/5 p-6 text-center text-sm text-white/65">
                  Aucun pin métropole ne correspond aux filtres.
                </div>
              )}
            </div>

            {sidePoints.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {sidePoints.map((point) => (
                  <button
                    key={point.key}
                    type="button"
                    className="rounded-md border border-white/15 bg-white/10 px-3 py-2 text-left text-xs text-white/75 transition hover:border-brand-gold hover:bg-white/15"
                    onClick={() => setActiveKey(point.key)}
                  >
                    <span className="font-semibold text-white">{point.label}</span>
                    <span className="ml-2">{formatNumber(countForPoint(point, filters))} AO</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <aside className="min-h-0 overflow-y-auto border-t border-white/15 p-4 sm:p-5 lg:border-l lg:border-t-0">
            {activePoint ? (
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold">{activePoint.label}</h3>
                    <p className="mt-1 text-xs text-white/60">{formatNumber(countForPoint(activePoint, filters))} AO dans le filtre</p>
                  </div>
                  <Badge tone={scoreTone(activePoint.highest_score)}>{activePoint.highest_score}/100</Badge>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(activePoint.status_counts).map(([status, count]) => (
                    <div key={status} className={["rounded-md border p-2", filters.status === status ? "border-brand-gold bg-brand-gold/15" : "border-white/15 bg-white/10"].join(" ")}>
                      <div className="text-white/55">{statusLabel(status)}</div>
                      <div className="mt-1 text-lg font-semibold">{formatNumber(count)}</div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 space-y-2">
                  {(activeOpportunities.length ? activeOpportunities : activePoint.opportunities).map((opportunity) => (
                    <Link
                      key={opportunity.id}
                      href={`/opportunities/${opportunity.id}`}
                      className="block rounded-md border border-white/15 bg-white/10 p-3 text-sm transition hover:border-brand-gold hover:bg-white/15"
                      onClick={() => setOpen(false)}
                    >
                      <div className="line-clamp-2 font-medium text-white">{opportunity.title}</div>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-white/60">
                        <Badge tone={scoreTone(opportunity.global_score)}>{opportunity.global_score}/100</Badge>
                        <span>{statusLabel(opportunity.status)}</span>
                        {opportunity.buyer ? <span>{opportunity.buyer}</span> : null}
                      </div>
                    </Link>
                  ))}
                </div>

                <Button asChild variant="secondary" className="mt-4 w-full">
                  <Link href={zoneHref(activePoint, filters)} onClick={() => setOpen(false)}>
                    Voir la zone filtrée
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="rounded-md border border-white/15 bg-white/10 p-3 text-sm text-white/65">
                {loading ? "Chargement de la carte..." : loadError ? "La carte est temporairement indisponible." : "Aucun point cartographique disponible avec ces filtres."}
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      <Button
        type="button"
        variant="secondary"
        className="rounded-full border-white bg-white px-4 text-brand-marine hover:bg-white/90"
        onClick={openMap}
        disabled={loading}
        title="Afficher la carte des AO détectés"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapPinned className="h-4 w-4" />}
        Carte AO
      </Button>

      {mounted && modal ? createPortal(modal, document.body) : null}
    </>
  );
}
