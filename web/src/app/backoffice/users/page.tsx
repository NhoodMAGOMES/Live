import { UserAdmin } from "@/components/user-admin";

export default function BackofficeUsersPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-5">
        <p className="text-sm font-semibold uppercase text-primary">Backoffice</p>
        <h1 className="mt-2 text-2xl font-semibold text-brand-marine">Profils utilisateurs</h1>
        <p className="text-sm text-foreground/60">Comptes autorisés à se connecter, rôles, statut actif et mots de passe.</p>
      </div>
      <UserAdmin />
    </div>
  );
}
