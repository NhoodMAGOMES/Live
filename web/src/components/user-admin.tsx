"use client";

import { FormEvent, useEffect, useState } from "react";
import { Plus, RefreshCw, Save, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_BASE, getAuthHeaders, type UserProfile } from "@/lib/api";

function authHeaders() {
  return {
    "Content-Type": "application/json",
    ...getAuthHeaders()
  };
}

function accessLabel(role: UserProfile["role"]) {
  return role === "admin" ? "Front + backoffice" : "Frontoffice seulement";
}

export function UserAdmin() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [busy, setBusy] = useState<number | "create" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    const response = await fetch(`${API_BASE}/auth/users`, { headers: authHeaders(), cache: "no-store" });
    if (!response.ok) {
      setError("Impossible de charger les profils. Vérifiez que votre compte est administrateur.");
      setUsers([]);
      return;
    }
    setUsers((await response.json()) as UserProfile[]);
  }

  useEffect(() => {
    refresh().catch(() => setError("API indisponible."));
  }, []);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy("create");
    setError(null);
    const response = await fetch(`${API_BASE}/auth/users`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
        full_name: form.get("full_name") || null,
        role: form.get("role")
      })
    });
    setBusy(null);
    if (!response.ok) {
      setError("Création impossible. Email déjà utilisé ou droits insuffisants.");
      return;
    }
    formElement.reset();
    await refresh();
  }

  async function updateUser(user: UserProfile, patch: Partial<UserProfile> & { password?: string }) {
    setBusy(user.id);
    setError(null);
    const response = await fetch(`${API_BASE}/auth/users/${user.id}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify(patch)
    });
    setBusy(null);
    if (!response.ok) {
      setError("Mise à jour impossible.");
      return;
    }
    await refresh();
  }

  async function deleteUser(user: UserProfile) {
    setBusy(user.id);
    setError(null);
    const response = await fetch(`${API_BASE}/auth/users/${user.id}`, {
      method: "DELETE",
      headers: authHeaders()
    });
    setBusy(null);
    if (!response.ok) {
      setError("Suppression impossible. Vous ne pouvez pas supprimer votre propre profil ou le dernier admin.");
      return;
    }
    await refresh();
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold">Créer un profil</h2>
        <form onSubmit={createUser} className="grid gap-3 lg:grid-cols-[1fr_1fr_220px_180px_auto]">
          <input name="full_name" placeholder="Nom" />
          <input name="email" type="email" placeholder="Email" required />
          <select name="role" defaultValue="analyst">
            <option value="analyst">Frontoffice seulement</option>
            <option value="admin">Frontoffice + backoffice</option>
          </select>
          <input name="password" type="password" placeholder="Mot de passe" required minLength={8} />
          <Button type="submit" disabled={busy === "create"}>
            <Plus className="h-4 w-4" />
            Ajouter
          </Button>
        </form>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border p-4">
          <div>
            <h2 className="text-sm font-semibold">Profils de connexion</h2>
            {error && <p className="mt-1 text-sm text-danger">{error}</p>}
          </div>
          <Button onClick={refresh} variant="secondary" size="sm">
            <RefreshCw className="h-4 w-4" />
            Actualiser
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Utilisateur</th>
                <th>Accès</th>
                <th>Statut</th>
                <th>Nouveau mot de passe</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div className="font-medium">{user.full_name || "Sans nom"}</div>
                    <div className="text-sm text-foreground/60">{user.email}</div>
                  </td>
                  <td>
                    <select
                      value={user.role === "admin" ? "admin" : "analyst"}
                      onChange={(event) => updateUser(user, { role: event.target.value as UserProfile["role"] })}
                      disabled={busy === user.id}
                    >
                      <option value="analyst">Frontoffice seulement</option>
                      <option value="admin">Frontoffice + backoffice</option>
                    </select>
                    <div className="mt-1 text-xs text-foreground/55">{accessLabel(user.role)}</div>
                  </td>
                  <td>
                    <button onClick={() => updateUser(user, { is_active: !user.is_active })} disabled={busy === user.id}>
                      <Badge tone={user.is_active ? "green" : "neutral"}>{user.is_active ? "Actif" : "Inactif"}</Badge>
                    </button>
                  </td>
                  <td>
	                    <form
	                      onSubmit={async (event) => {
	                        event.preventDefault();
	                        const formElement = event.currentTarget;
	                        const form = new FormData(formElement);
	                        const password = String(form.get("password") || "");
	                        if (password) await updateUser(user, { password });
	                        formElement.reset();
	                      }}
                      className="flex gap-2"
                    >
                      <input name="password" type="password" placeholder="Min. 8 caractères" minLength={8} />
                      <Button type="submit" size="icon" variant="secondary" title="Mettre à jour">
                        <Save className="h-4 w-4" />
                      </Button>
                    </form>
                  </td>
                  <td>
                    <Button onClick={() => deleteUser(user)} disabled={busy === user.id} size="icon" variant="danger" title="Supprimer">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr>
                  <td colSpan={5} className="text-sm text-foreground/60">
                    Aucun profil affiché.
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
