"use client";

import { ArrowRight, LockKeyhole, Mail, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api";

const liveHeroImage =
  "https://www.nhood.com/var/site/storage/images/0/0/5/5/975500-1-fre-FR/907dce2adfe9-shutterstock_2080757623.jpg";

export function LoginHome() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (window.localStorage.getItem("live_pulse_token")) {
      router.replace("/frontoffice");
    }
  }, [router]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password")
      })
    });
    if (!response.ok) {
      setBusy(false);
      setError("Identifiants incorrects ou profil inactif.");
      return;
    }
    const token = (await response.json()) as { access_token: string };
    window.localStorage.setItem("live_pulse_token", token.access_token);
    const me = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token.access_token}` }
    });
    if (me.ok) {
      window.localStorage.setItem("live_pulse_user", JSON.stringify(await me.json()));
    }
    router.replace("/frontoffice");
  }

  return (
    <div
      className="relative min-h-screen overflow-hidden bg-brand-marine text-white"
      style={{
        backgroundImage: `linear-gradient(110deg, rgba(0, 45, 87, 0.88) 0%, rgba(0, 137, 63, 0.62) 46%, rgba(158, 57, 132, 0.42) 100%), url(${liveHeroImage})`,
        backgroundPosition: "center",
        backgroundSize: "cover"
      }}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_15%,rgba(255,255,255,0.20),transparent_24%),linear-gradient(180deg,rgba(0,0,0,0.05),rgba(0,0,0,0.42))]" />

      <div className="relative mx-auto grid min-h-screen w-full max-w-7xl grid-cols-1 gap-8 overflow-x-hidden px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_430px] lg:items-center lg:px-8">
        <section className="min-w-0 max-w-[358px] pt-10 sm:max-w-3xl lg:pt-0">
          <div className="mb-10 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-md bg-white text-sm font-semibold text-primary shadow-lg">
              LP
            </div>
            <div>
              <p className="text-base font-semibold">LIVE Pulse</p>
              <p className="text-xs font-medium uppercase text-white/60">AO Intelligence by Nhood</p>
            </div>
          </div>

          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold uppercase text-white/80 backdrop-blur-md">
            <Sparkles className="h-3.5 w-3.5 text-brand-gold" />
            Lieux vivants, décisions rapides
          </div>

          <h1 className="max-w-[358px] break-words text-3xl font-semibold leading-tight text-white sm:max-w-3xl sm:text-5xl">
            Détecter les appels d'offres qui font vibrer les lieux.
          </h1>

          <p className="mt-5 max-w-[358px] text-base leading-7 text-white/80 sm:max-w-2xl">
            Un cockpit métier pour qualifier les opportunités, suivre les agents IA et transformer les actifs en destinations attractives.
          </p>

          <div className="mt-10 grid max-w-[358px] gap-3 sm:max-w-2xl sm:grid-cols-3">
            {["Hospitality venues", "Event programming", "Médias & naming"].map((item) => (
              <div key={item} className="rounded-md border border-white/20 bg-white/10 px-4 py-3 text-sm font-medium text-white/90 backdrop-blur-md">
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full min-w-0 max-w-[358px] rounded-lg border border-white/20 bg-white/20 p-5 shadow-2xl backdrop-blur-xl sm:max-w-[430px] sm:p-7">
          <div className="mb-6 text-center">
            <p className="text-sm font-semibold uppercase text-white/60">Bienvenue</p>
            <h2 className="mt-2 text-3xl font-semibold">Connexion</h2>
            <p className="mt-2 text-sm text-white/70">Accès direct au frontoffice métier.</p>
          </div>
          <form onSubmit={login} className="mt-5 space-y-3">
            <label className="block text-sm font-medium text-white/90">
              Email
              <span className="relative mt-1 block">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/60" />
                <input
                  className="w-full rounded-full border-white/25 bg-white/10 py-3 pl-10 pr-4 text-white placeholder:text-white/40 focus:border-white/70 focus:ring-white/20"
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="prenom.nom@nhood.com"
                  required
                />
              </span>
            </label>
            <label className="block text-sm font-medium text-white/90">
              Mot de passe
              <span className="relative mt-1 block">
                <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/60" />
                <input
                  className="w-full rounded-full border-white/25 bg-white/10 py-3 pl-10 pr-4 text-white placeholder:text-white/40 focus:border-white/70 focus:ring-white/20"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="Mot de passe"
                  required
                />
              </span>
            </label>
            <div className="flex items-center justify-between gap-3 text-xs text-white/70">
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" className="h-3.5 w-3.5 rounded border-white/30 bg-white/10 p-0" />
                Mémoriser
              </label>
              <span>Accès sécurisé</span>
            </div>
            {error && <p className="rounded-md bg-danger/20 px-3 py-2 text-sm text-white">{error}</p>}
            <Button type="submit" className="mt-2 w-full rounded-full border-white bg-white py-5 text-brand-marine hover:bg-white/90" disabled={busy}>
              {busy ? "Connexion..." : "Entrer dans le frontoffice"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        </section>
      </div>
    </div>
  );
}
