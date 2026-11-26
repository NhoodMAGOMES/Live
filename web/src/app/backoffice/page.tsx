import Link from "next/link";
import { Bot, Database, KeyRound, Users } from "lucide-react";

import { Card } from "@/components/ui/card";

const areas = [
  {
    href: "/backoffice/platforms",
    label: "Connexions plateformes",
    description: "Sources AO, endpoints, activation, derniers runs et erreurs de collecte.",
    icon: Database
  },
  {
    href: "/backoffice/agents",
    label: "Paramètres agents",
    description: "Activation, cycles automatiques, exécutions, tokens et taux de réussite.",
    icon: Bot
  },
  {
    href: "/backoffice/users",
    label: "Profils utilisateurs",
    description: "Création, rôles, statut, réinitialisation de mot de passe et suppression.",
    icon: Users
  },
  {
    href: "/backoffice/keywords",
    label: "Paramétrage mots-clés",
    description: "Familles métier, poids, synonymes et activation du scoring AO.",
    icon: KeyRound
  }
];

export default function BackofficePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-6">
        <p className="text-sm font-semibold uppercase text-primary">Backoffice</p>
        <h1 className="mt-2 text-2xl font-semibold text-brand-marine">Administration LIVE Pulse</h1>
        <p className="mt-2 max-w-3xl text-sm text-foreground/60">
          Un espace séparé du métier pour piloter les connexions, les agents, les droits d'accès et les règles de scoring.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {areas.map((area) => {
          const Icon = area.icon;
          return (
            <Link key={area.href} href={area.href}>
              <Card className="flex h-full flex-col p-5 transition hover:border-primary/40 hover:shadow-md">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary-extra-light text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <h2 className="mt-4 text-base font-semibold text-brand-marine">{area.label}</h2>
                <p className="mt-2 text-sm leading-6 text-foreground/60">{area.description}</p>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
