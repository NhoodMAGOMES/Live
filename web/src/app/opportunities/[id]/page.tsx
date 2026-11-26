import { notFound } from "next/navigation";
import { ArrowRight, Bot, Clock3, Download, ExternalLink, FileText, UserRound } from "lucide-react";

import { OpportunityActions } from "@/components/opportunity-actions";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { API_PUBLIC_BASE, getOpportunity, getOpportunityAudit, getOpportunityDocuments, getReport } from "@/lib/api";
import type { OpportunityAudit, OpportunityDocument } from "@/lib/api";

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

async function load(id: string) {
  try {
    const opportunity = await getOpportunity(id);
    const [reportResult, documentsResult, auditResult] = await Promise.allSettled([
      getReport(id),
      getOpportunityDocuments(id),
      getOpportunityAudit(id)
    ]);
    const report = reportResult.status === "fulfilled" ? reportResult.value : null;
    const documents: OpportunityDocument[] = documentsResult.status === "fulfilled" ? documentsResult.value : [];
    const audit: OpportunityAudit[] = auditResult.status === "fulfilled" ? auditResult.value : [];
    return { opportunity, report, documents, audit };
  } catch {
    notFound();
  }
}

function reportHtmlFragment(html: string) {
  const withoutStyle = html.replace(/<style[\s\S]*?<\/style>/gi, "");
  const bodyMatch = withoutStyle.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch?.[1]) return bodyMatch[1];
  return withoutStyle.replace(/<!doctype[^>]*>/gi, "").replace(/<\/?(html|head|meta)[^>]*>/gi, "");
}

function textValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(value: unknown) {
  return typeof value === "number" ? value : null;
}

function originLabel(origin: unknown) {
  return (
    {
      detail_actions: "Fiche AO",
      catalog_quick_select: "Catalogue AO",
      detail_analysis: "Analyse depuis la fiche",
      batch_analysis: "Analyse groupée",
      manual_status_update: "Mise à jour manuelle"
    }[String(origin || "")] || null
  );
}

function auditTransition(entry: OpportunityAudit) {
  const transition = entry.transition || {};
  const beforeStatus = textValue(transition.from_status) || textValue(entry.before?.status);
  const afterStatus = textValue(transition.to_status) || textValue(entry.after?.status);
  return {
    before: textValue(transition.from_status_label) || (beforeStatus ? statusLabel(beforeStatus) : null),
    after: textValue(transition.to_status_label) || (afterStatus ? statusLabel(afterStatus) : null)
  };
}

export default async function OpportunityDetailPage({ params }: { params: { id: string } }) {
  const { opportunity, report, documents, audit } = await load(params.id);
  const summary = opportunity.ai_summary?.split("\n").filter(Boolean) ?? [];
  const reportHtml = report?.html ? reportHtmlFragment(report.html) : null;
  const hasDocumentAccess = Boolean(opportunity.source_url) || documents.length > 0;
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-4xl rounded-lg border border-white/20 bg-white/20 p-5 text-white shadow-2xl backdrop-blur-xl sm:p-6">
          <div className="mb-2 flex flex-wrap gap-2">
            <Badge tone="blue">{opportunity.source}</Badge>
            <Badge>{statusLabel(opportunity.status)}</Badge>
            <Badge tone={opportunity.global_score >= 65 ? "green" : opportunity.global_score >= 45 ? "amber" : "red"}>
              {opportunity.global_score}/100
            </Badge>
          </div>
          <h1 className="text-3xl font-semibold leading-tight">{opportunity.title}</h1>
          <p className="mt-2 text-sm text-white/70">{opportunity.buyer || "Acheteur non disponible"}</p>
        </div>
        <OpportunityActions id={opportunity.id} currentStatus={opportunity.status} />
      </div>

      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <span className="text-sm text-white/70">Décision</span>
          <div className="mt-2 text-2xl font-semibold">{statusLabel(opportunity.status)}</div>
        </div>
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <span className="text-sm text-white/70">Score</span>
          <div className="mt-2 text-2xl font-semibold">{opportunity.global_score}/100</div>
        </div>
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <span className="text-sm text-white/70">Acheteur</span>
          <div className="mt-2 text-lg font-semibold">{opportunity.buyer || "Non disponible"}</div>
        </div>
        <div className="rounded-md border border-white/20 bg-white/20 p-4 text-white shadow-lg backdrop-blur-xl">
          <span className="text-sm text-white/70">Deadline</span>
          <div className="mt-2 text-lg font-semibold">
            {opportunity.deadline ? new Date(opportunity.deadline).toLocaleDateString("fr-FR") : "Non disponible"}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <Card className="front-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Métadonnées</h2>
          <dl className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-md border border-white/15 bg-white/10 p-3"><dt className="text-white/60">Source</dt><dd>{opportunity.source}</dd></div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3"><dt className="text-white/60">Référence</dt><dd>{opportunity.source_reference || "Non disponible"}</dd></div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3"><dt className="text-white/60">Procédure</dt><dd>{opportunity.procedure || "Non disponible"}</dd></div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3"><dt className="text-white/60">Localisation</dt><dd>{opportunity.location || "Non disponible"}</dd></div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3"><dt className="text-white/60">Date limite</dt><dd>{opportunity.deadline ? new Date(opportunity.deadline).toLocaleString("fr-FR") : "Non disponible"}</dd></div>
            <div className="rounded-md border border-white/15 bg-white/10 p-3"><dt className="text-white/60">CPV</dt><dd>{opportunity.cpv?.join(", ") || "Non disponible"}</dd></div>
          </dl>
        </Card>

        <Card className="front-panel p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">Documents de l'appel d'offre</h2>
              <p className="mt-1 text-sm text-white/70">Pièces disponibles pour contrôler l'avis, le règlement et le dossier source.</p>
            </div>
            <Badge>{documents.length} fichier(s)</Badge>
          </div>
          {hasDocumentAccess ? (
            <div className="grid gap-3 md:grid-cols-2">
              {opportunity.source_url ? (
                <a
                  href={opportunity.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between gap-3 rounded-md border border-white/15 bg-white/10 p-3 text-sm text-white transition hover:border-brand-gold hover:bg-white/15"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <ExternalLink className="h-4 w-4 shrink-0 text-brand-gold" />
                    <span className="min-w-0">
                      <span className="block font-semibold">Source officielle</span>
                      <span className="block truncate text-white/70">{opportunity.source_url}</span>
                    </span>
                  </span>
                  <ExternalLink className="h-4 w-4 shrink-0 text-white/70" />
                </a>
              ) : null}
              {documents.map((document) => (
                <a
                  key={document.id}
                  href={`${API_PUBLIC_BASE}/opportunities/${opportunity.id}/documents/${document.id}/download`}
                  className="flex items-center justify-between gap-3 rounded-md border border-white/15 bg-white/10 p-3 text-sm text-white transition hover:border-brand-gold hover:bg-white/15"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <FileText className="h-4 w-4 shrink-0 text-brand-gold" />
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{document.filename}</span>
                      <span className="block text-white/70">
                        {document.content_type || "Fichier AO"} - importé le {new Date(document.created_at).toLocaleDateString("fr-FR")}
                      </span>
                    </span>
                  </span>
                  <Download className="h-4 w-4 shrink-0 text-white/70" />
                </a>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-white/15 bg-white/10 p-3 text-sm text-white/70">
              Aucun document n'est encore attaché à cet AO. Importez un dossier ou ouvrez la plateforme source quand elle fournit les pièces.
            </div>
          )}
        </Card>

        <Card className="front-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Score par famille</h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Object.entries(opportunity.score_by_family || {}).map(([family, score]) => (
              <div key={family} className="rounded-md border border-white/15 bg-white/10 p-3">
                <div className="mb-2 flex justify-between gap-3 text-xs">
                  <span>{family}</span>
                  <span className="font-medium">{score}</span>
                </div>
                <div className="h-2 rounded-sm bg-white/20">
                  <div className="h-2 rounded-sm bg-brand-gold" style={{ width: `${Math.min(100, Number(score))}%` }} />
                </div>
              </div>
            ))}
            {!Object.keys(opportunity.score_by_family || {}).length && <p className="text-sm text-white/70">Analyse à lancer.</p>}
          </div>
        </Card>

        <Card className="front-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Synthèse métier</h2>
          {summary.length ? (
            <ul className="grid gap-2 text-sm leading-6 md:grid-cols-2">
              {summary.slice(0, 6).map((item) => (
                <li key={item} className="rounded-md border border-white/15 bg-white/10 p-3">{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-white/70">Aucune synthèse disponible. Lancez l'analyse AO.</p>
          )}
        </Card>

        <Card className="front-panel p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">Historique des décisions</h2>
              <p className="mt-1 text-sm text-white/70">Qui a changé l'état, quand, depuis quel écran et vers quelle décision.</p>
            </div>
            <Badge>{audit.length} action(s)</Badge>
          </div>
          {audit.length ? (
            <div className="space-y-3">
              {audit.slice(0, 12).map((entry) => {
                const transition = auditTransition(entry);
                const score = numberValue(entry.after?.score);
                const origin = originLabel(entry.after?.origin);
                return (
                  <div key={entry.id} className="rounded-md border border-white/15 bg-white/10 p-3 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-2">
                        {entry.action === "analysis_run" ? (
                          <Bot className="h-4 w-4 shrink-0 text-brand-gold" />
                        ) : (
                          <UserRound className="h-4 w-4 shrink-0 text-brand-gold" />
                        )}
                        <div className="min-w-0">
                          <div className="font-medium text-white">{entry.action_label || "Action"}</div>
                          <div className="mt-0.5 text-xs text-white/60">
                            par {entry.actor_label}{entry.actor_role ? ` · ${entry.actor_role}` : ""}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-white/60">
                        <Clock3 className="h-3.5 w-3.5" />
                        {new Date(entry.created_at).toLocaleString("fr-FR")}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-white/80">
                      {transition.before ? <Badge>{transition.before}</Badge> : null}
                      {transition.before || transition.after ? <ArrowRight className="h-4 w-4 text-white/50" /> : null}
                      {transition.after ? <Badge tone="blue">{transition.after}</Badge> : null}
                      {score !== null ? <Badge tone={score >= 65 ? "green" : score >= 45 ? "amber" : "red"}>Score {score}/100</Badge> : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-white/60">
                      {origin ? <span>Origine: {origin}</span> : null}
                      {entry.action === "status_update" ? <span>Transition manuelle tracée</span> : null}
                      {entry.action === "analysis_run" ? <span>Transition issue de l'analyse IA</span> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-white/70">Aucune action métier tracée pour le moment.</p>
          )}
        </Card>

        <Card className="front-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Objet</h2>
          <p className="whitespace-pre-wrap text-sm leading-6">{opportunity.description || opportunity.object || "Non disponible"}</p>
        </Card>

        <Card className="front-panel overflow-hidden">
          <div className="border-b border-border p-4">
            <h2 className="text-sm font-semibold">Mots-clés détectés</h2>
          </div>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr><th>Famille</th><th>Mot-clé</th><th>Extrait</th><th>Poids</th></tr>
              </thead>
              <tbody>
                {(opportunity.keyword_traces || []).map((trace, index) => (
                  <tr key={index}>
                    <td>{String(trace.category || "Non disponible")}</td>
                    <td>{String(trace.keyword || trace.matched_term || "Non disponible")}</td>
                    <td className="max-w-xl text-sm">{String(trace.excerpt || "Non disponible")}</td>
                    <td>{String(trace.weight || "")}</td>
                  </tr>
                ))}
                {!opportunity.keyword_traces?.length && <tr><td colSpan={4} className="text-sm text-white/70">Aucun match enregistré.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="front-panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Rapport</h2>
          {reportHtml ? (
            <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: reportHtml }} />
          ) : (
            <p className="text-sm text-white/70">Aucun rapport généré.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
