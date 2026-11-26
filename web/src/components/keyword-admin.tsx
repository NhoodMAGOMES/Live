"use client";

import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_BASE, getAuthHeaders, getKeywordData, type Keyword, type KeywordCategory } from "@/lib/api";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders()
  };
}

export function KeywordAdmin() {
  const [categories, setCategories] = useState<KeywordCategory[]>([]);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    const data = await getKeywordData();
    setCategories(data.categories);
    setKeywords(data.keywords);
    setLoading(false);
  }

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, []);

  async function createCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await fetch(`${API_BASE}/keyword-categories`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ name: form.get("name"), threshold: Number(form.get("threshold") || 8), strategic_tags: ["Pulse LIVE"] })
    });
    formElement.reset();
    await refresh();
  }

  async function createKeyword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await fetch(`${API_BASE}/keywords`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        category_id: Number(form.get("category_id")),
        term: form.get("term"),
        weight: Number(form.get("weight") || 3),
        synonyms: String(form.get("synonyms") || "")
          .split("|")
          .map((item) => item.trim())
          .filter(Boolean)
      })
    });
    formElement.reset();
    await refresh();
  }

  async function toggleKeyword(keyword: Keyword) {
    await fetch(`${API_BASE}/keywords/${keyword.id}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ is_active: !keyword.is_active })
    });
    await refresh();
  }

  async function deleteKeyword(id: number) {
    await fetch(`${API_BASE}/keywords/${id}`, { method: "DELETE", headers: getAuthHeaders() });
    await refresh();
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold">Famille</h2>
          <form onSubmit={createCategory} className="grid gap-3 sm:grid-cols-[1fr_120px_auto]">
            <input name="name" placeholder="Nom famille" required />
            <input name="threshold" placeholder="Seuil" type="number" min="0" step="1" />
            <Button type="submit">
              <Plus className="h-4 w-4" />
              Ajouter
            </Button>
          </form>
        </Card>
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold">Mot-clé</h2>
          <form onSubmit={createKeyword} className="grid gap-3 md:grid-cols-[1fr_1fr_90px_1fr_auto]">
            <select name="category_id" required>
              <option value="">Famille</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
            <input name="term" placeholder="Mot-clé" required />
            <input name="weight" placeholder="Poids" type="number" min="0" step="0.5" />
            <input name="synonyms" placeholder="Synonymes avec |" />
            <Button type="submit">
              <Plus className="h-4 w-4" />
              Ajouter
            </Button>
          </form>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 className="text-sm font-semibold">Base mots-clés</h2>
          <Button onClick={refresh} variant="secondary" size="sm">
            <RefreshCw className="h-4 w-4" />
            Actualiser
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr><th>Mot-clé</th><th>Famille</th><th>Poids</th><th>Synonymes</th><th>Statut</th><th /></tr>
            </thead>
            <tbody>
              {keywords.map((keyword) => {
                const category = categories.find((item) => item.id === keyword.category_id);
                return (
                  <tr key={keyword.id}>
                    <td className="font-medium">{keyword.term}</td>
                    <td>{category?.name || keyword.category_id}</td>
                    <td>{keyword.weight}</td>
                    <td>{keyword.synonyms.map((item) => item.term).join(", ") || "Non disponible"}</td>
                    <td>
                      <button onClick={() => toggleKeyword(keyword)}>
                        <Badge tone={keyword.is_active ? "green" : "neutral"}>{keyword.is_active ? "Actif" : "Inactif"}</Badge>
                      </button>
                    </td>
                    <td>
                      <Button onClick={() => deleteKeyword(keyword.id)} variant="ghost" size="icon" title="Supprimer">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {!keywords.length && (
                <tr>
                  <td colSpan={6} className="text-sm text-foreground/60">
                    {loading ? "Chargement..." : "Aucun mot-clé."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
