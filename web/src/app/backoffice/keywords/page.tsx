import { KeywordAdmin } from "@/components/keyword-admin";

export default function BackofficeKeywordsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-5">
        <p className="text-sm font-semibold uppercase text-primary">Backoffice</p>
        <h1 className="mt-2 text-2xl font-semibold text-brand-marine">Paramétrage mots-clés</h1>
        <p className="text-sm text-foreground/60">Familles, poids, synonymes et activation utilisés par le scoring AO.</p>
      </div>
      <KeywordAdmin />
    </div>
  );
}
