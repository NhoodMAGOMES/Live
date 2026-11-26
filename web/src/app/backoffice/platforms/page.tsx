import { SourceAdmin } from "@/components/source-admin";

export default function BackofficePlatformsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-5">
        <p className="text-sm font-semibold uppercase text-primary">Backoffice</p>
        <h1 className="mt-2 text-2xl font-semibold text-brand-marine">Connexions plateformes</h1>
        <p className="text-sm text-foreground/60">Connecteurs AO, fonctionnement, volumes récupérés et activation par source.</p>
      </div>
      <SourceAdmin />
    </div>
  );
}
