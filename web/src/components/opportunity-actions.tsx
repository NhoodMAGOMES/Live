"use client";

import { useRouter } from "next/navigation";
import { Download, Play, Save } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { API_BASE, getAuthHeaders, updateOpportunityStatus } from "@/lib/api";

export function OpportunityActions({ id, currentStatus }: { id: number; currentStatus: string }) {
  const router = useRouter();
  const [status, setStatus] = useState(currentStatus);
  const [busy, setBusy] = useState(false);

  async function analyze() {
    setBusy(true);
    try {
      await fetch(`${API_BASE}/opportunities/${id}/analyze`, { method: "POST", headers: getAuthHeaders() });
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function saveStatus() {
    setBusy(true);
    try {
      await updateOpportunityStatus(id, status, "detail_actions");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={analyze} disabled={busy}>
        <Play className="h-4 w-4" />
        Relancer l'analyse IA
      </Button>
      <select
        value={status}
        onChange={(event) => setStatus(event.target.value)}
        className="h-9 min-w-[14.5rem] border-white/40 bg-white px-3 font-medium text-brand-marine shadow-sm"
        title="Décision métier LIVE"
      >
        <optgroup label="Traitement IA">
          <option value="nouveau">À analyser par IA</option>
          <option value="analyse">Revue IA terminée</option>
        </optgroup>
        <optgroup label="Décision LIVE">
          <option value="a_qualifier">À qualifier par l'équipe</option>
          <option value="pertinent">Pertinent pour LIVE</option>
          <option value="go">En étude réponse</option>
          <option value="watch">Sous surveillance</option>
        </optgroup>
        <optgroup label="Sortie">
          <option value="non_pertinent">Écarté par IA</option>
          <option value="no_go">NO-GO métier</option>
          <option value="archive">Archivé</option>
        </optgroup>
      </select>
      <Button onClick={saveStatus} variant="secondary" disabled={busy}>
        <Save className="h-4 w-4" />
        Enregistrer décision
      </Button>
      <Button asChild variant="secondary">
        <a href={`${API_BASE}/opportunities/${id}/export/pdf`}>
          <Download className="h-4 w-4" />
          Export
        </a>
      </Button>
    </div>
  );
}
