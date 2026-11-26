import { AgentConsole } from "@/components/agent-console";

export default function BackofficeAgentsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-5">
        <p className="text-sm font-semibold uppercase text-primary">Backoffice</p>
        <h1 className="mt-2 text-2xl font-semibold text-brand-marine">Paramètres agents</h1>
        <p className="text-sm text-foreground/60">
          Recherche manuelle par mots-clés LIVE, planification automatique, activation, exécutions, consommation tokens et réussite par agent.
        </p>
      </div>
      <AgentConsole />
    </div>
  );
}
