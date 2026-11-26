"use client";

import { FileUp, LinkIcon, Plus } from "lucide-react";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_BASE } from "@/lib/api";

export function ImportOpportunity() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function importManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    const form = new FormData(formElement);
    await fetch(`${API_BASE}/opportunities/import-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: form.get("source") || "manual",
        source_url: form.get("source_url") || null,
        source_reference: form.get("source_reference") || null,
        title: form.get("title"),
        buyer: form.get("buyer") || null,
        description: form.get("description"),
        location: form.get("location") || null
      })
    });
    setBusy(false);
    formElement.reset();
    router.refresh();
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    await fetch(`${API_BASE}/opportunities/import-file`, { method: "POST", body: data });
    setBusy(false);
    form.reset();
    router.refresh();
  }

  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen((value) => !value)} variant="secondary">
        <Plus className="h-4 w-4" />
        Import
      </Button>
      {open && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="front-panel p-4">
            <h2 className="mb-3 text-sm font-semibold">Import manuel</h2>
            <form onSubmit={importManual} className="grid gap-3">
              <div className="grid gap-3 md:grid-cols-2">
                <input name="source" placeholder="Source" />
                <input name="source_url" placeholder="Lien source" />
                <input name="source_reference" placeholder="Référence" />
                <input name="buyer" placeholder="Acheteur" />
                <input name="location" placeholder="Localisation" />
                <input name="title" placeholder="Titre" required />
              </div>
              <textarea name="description" placeholder="Texte AO" required rows={5} />
              <Button type="submit" disabled={busy}>
                <LinkIcon className="h-4 w-4" />
                Créer
              </Button>
            </form>
          </Card>
          <Card className="front-panel p-4">
            <h2 className="mb-3 text-sm font-semibold">Import fichier</h2>
            <form onSubmit={uploadFile} className="grid gap-3">
              <input name="file" type="file" required />
              <Button type="submit" disabled={busy}>
                <FileUp className="h-4 w-4" />
                Importer
              </Button>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
