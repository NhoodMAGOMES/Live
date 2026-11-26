"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Bell,
  Bot,
  CheckCircle2,
  ChevronsLeft,
  ChevronsRight,
  Clock,
  Database,
  Eye,
  Gauge,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Scale,
  SearchCheck,
  Send,
  Sparkles,
  Users,
  XCircle
} from "lucide-react";
import { useEffect, useState } from "react";

import { API_BASE, canAccessBackoffice, getAuthHeaders, getStoredUser, type UserProfile } from "@/lib/api";

const liveHeroImage = "/live-nhood-background.jpg";

const frontItems = [
  { href: "/frontoffice", label: "Dashboard", icon: Gauge },
  { href: "/opportunities", label: "Opportunités AO", icon: ListChecks }
];

const simpleFrontItems = [
  { href: "/frontoffice", label: "Dashboard", icon: Gauge, processed: false },
  { href: "/opportunities", label: "Opportunités", icon: ListChecks, processed: false },
  { href: "/opportunities?processed=true", label: "Décisions", icon: Scale, processed: true }
];

type InterfaceMode = "simple" | "advanced";

const INTERFACE_MODE_KEY = "live_pulse_interface_mode";

const phaseItems = [
  { href: "/opportunities?status=nouveau", label: "À analyser", icon: Clock, status: "nouveau" },
  { href: "/opportunities?processed=true", label: "Revue IA", icon: CheckCircle2, processed: true },
  { href: "/opportunities?status=a_qualifier", label: "À qualifier", icon: SearchCheck, status: "a_qualifier" },
  { href: "/opportunities?status=pertinent", label: "Pertinents", icon: Sparkles, status: "pertinent" },
  { href: "/opportunities?status=go", label: "En étude réponse", icon: Send, status: "go" },
  { href: "/opportunities?status=watch", label: "Sous surveillance", icon: Eye, status: "watch" },
  { href: "/opportunities?status=non_pertinent", label: "Écartés par IA", icon: XCircle, status: "non_pertinent" }
];

const backItems = [
  { href: "/backoffice", label: "Accueil", icon: LayoutDashboard },
  { href: "/backoffice/platforms", label: "Plateformes", icon: Database },
  { href: "/backoffice/agents", label: "Agents", icon: Bot },
  { href: "/backoffice/users", label: "Profils", icon: Users },
  { href: "/backoffice/keywords", label: "Mots-clés", icon: KeyRound }
];

function legacyBackofficeTarget(pathname: string) {
  if (pathname === "/agents") return "/backoffice/agents";
  if (pathname.startsWith("/admin/sources")) return "/backoffice/platforms";
  if (pathname.startsWith("/admin/keywords")) return "/backoffice/keywords";
  return null;
}

function displayName(user: UserProfile | null) {
  return user?.full_name || user?.email || "Utilisateur";
}

function initials(user: UserProfile | null) {
  const name = displayName(user);
  const parts = name.split(/[.\s@_-]+/).filter(Boolean);
  return (parts[0]?.[0] || "U").toUpperCase() + (parts[1]?.[0] || "").toUpperCase();
}

function TopBar({
  currentUser,
  interfaceMode = "advanced",
  onInterfaceModeChange,
  variant = "front"
}: {
  currentUser: UserProfile | null;
  interfaceMode?: InterfaceMode;
  onInterfaceModeChange?: (mode: InterfaceMode) => void;
  variant?: "front" | "back";
}) {
  const isFront = variant === "front";
  return (
    <header
      className={[
        "frontoffice-topbar sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b px-4 backdrop-blur-xl lg:px-8",
        isFront ? "border-white/10 bg-white/10 text-white" : "border-border bg-white/90 text-foreground"
      ].join(" ")}
    >
      {isFront && onInterfaceModeChange ? (
        <div className="interface-mode-switch flex items-center rounded-md border border-white/15 bg-white/10 p-1" role="group" aria-label="Niveau de détail de l'interface">
          <button
            type="button"
            className={interfaceMode === "simple" ? "is-active" : ""}
            onClick={() => onInterfaceModeChange("simple")}
            aria-pressed={interfaceMode === "simple"}
          >
            Simplifiée
          </button>
          <button
            type="button"
            className={interfaceMode === "advanced" ? "is-active" : ""}
            onClick={() => onInterfaceModeChange("advanced")}
            aria-pressed={interfaceMode === "advanced"}
          >
            Avancée
          </button>
        </div>
      ) : <div />}
      <div className="flex items-center gap-3">
        <Link
          href="/notifications"
          className={[
            "topbar-action flex h-9 w-9 items-center justify-center rounded-md border transition",
            isFront ? "border-white/15 bg-white/10 text-white/80 hover:bg-white/15 hover:text-white" : "border-border bg-white text-foreground/70 hover:text-primary"
          ].join(" ")}
          title="Notifications"
        >
          <Bell className="h-4 w-4" />
        </Link>
        <div className={["topbar-profile flex items-center gap-3 rounded-full border py-1 pl-1 pr-3", isFront ? "border-white/15 bg-white/10" : "border-border bg-white"].join(" ")}>
          <div className={["topbar-avatar flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold", isFront ? "bg-white text-primary" : "bg-primary text-white"].join(" ")}>
            {initials(currentUser)}
          </div>
          <div className="min-w-0">
            <p className="max-w-[190px] truncate text-sm font-semibold">{displayName(currentUser)}</p>
          </div>
        </div>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [interfaceMode, setInterfaceMode] = useState<InterfaceMode>("advanced");
  const isAuthPage = pathname === "/";
  const isBackofficePage = pathname.startsWith("/backoffice") || pathname === "/agents" || pathname.startsWith("/admin");

  useEffect(() => {
    let cancelled = false;
    async function hydrateSession() {
      if (isAuthPage) {
        setIsReady(true);
        return;
      }

      const cachedUser = getStoredUser();
      if (cachedUser) {
        setCurrentUser(cachedUser);
        setIsReady(true);
      } else {
        setIsReady(false);
        setCurrentUser(null);
      }

      const token = window.localStorage.getItem("live_pulse_token");
      if (!token) {
        router.replace("/");
        return;
      }

      let user = cachedUser;
      try {
        const response = await fetch(`${API_BASE}/auth/me`, { headers: getAuthHeaders(), cache: "no-store" });
        if (response.ok) {
          user = (await response.json()) as UserProfile;
          window.localStorage.setItem("live_pulse_user", JSON.stringify(user));
        } else if (response.status === 401 || response.status === 403) {
          user = null;
        }
      } catch {
        user = getStoredUser();
      }

      if (!user) {
        window.localStorage.removeItem("live_pulse_token");
        window.localStorage.removeItem("live_pulse_user");
        router.replace("/");
        return;
      }

      if (isBackofficePage && !canAccessBackoffice(user)) {
        router.replace("/frontoffice");
        return;
      }

      const legacyTarget = legacyBackofficeTarget(pathname);
      if (legacyTarget) {
        router.replace(legacyTarget);
        return;
      }

      if (!cancelled) {
        setCurrentUser(user);
        setIsReady(true);
      }
    }

    hydrateSession();
    return () => {
      cancelled = true;
    };
  }, [isAuthPage, isBackofficePage, pathname, router]);

  useEffect(() => {
    const storedMode = window.localStorage.getItem(INTERFACE_MODE_KEY);
    if (storedMode === "simple" || storedMode === "advanced") {
      setInterfaceMode(storedMode);
    }
  }, []);

  function changeInterfaceMode(mode: InterfaceMode) {
    setInterfaceMode(mode);
    window.localStorage.setItem(INTERFACE_MODE_KEY, mode);
  }

  function logout() {
    window.localStorage.removeItem("live_pulse_token");
    window.localStorage.removeItem("live_pulse_user");
    router.replace("/");
  }

  if (isAuthPage) {
    return <main>{children}</main>;
  }

  if (!isReady) {
    return <main className="min-h-screen bg-background" />;
  }

  if (pathname.startsWith("/backoffice")) {
    return (
      <BackofficeShell pathname={pathname} currentUser={currentUser} onLogout={logout}>
        {children}
      </BackofficeShell>
    );
  }

  return (
    <FrontofficeShell
      pathname={pathname}
      currentUser={currentUser}
      interfaceMode={interfaceMode}
      onInterfaceModeChange={changeInterfaceMode}
      onLogout={logout}
    >
      {children}
    </FrontofficeShell>
  );
}

function FrontofficeShell({
  children,
  currentUser,
  interfaceMode,
  onInterfaceModeChange,
  onLogout,
  pathname
}: {
  children: React.ReactNode;
  currentUser: UserProfile | null;
  interfaceMode: InterfaceMode;
  onInterfaceModeChange: (mode: InterfaceMode) => void;
  onLogout: () => void;
  pathname: string;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const searchParams = useSearchParams();

  return (
    <div
      className="frontoffice-root relative min-h-screen overflow-hidden bg-brand-marine text-white lg:h-screen"
      data-interface-mode={interfaceMode}
      style={{
        backgroundImage: `linear-gradient(118deg, rgba(0, 45, 87, 0.94) 0%, rgba(0, 137, 63, 0.72) 48%, rgba(158, 57, 132, 0.36) 100%), url(${liveHeroImage})`,
        backgroundPosition: "center",
        backgroundSize: "cover"
      }}
    >
      <div className="frontoffice-overlay absolute inset-0 bg-[radial-gradient(circle_at_22%_12%,rgba(255,255,255,0.18),transparent_22%),linear-gradient(180deg,rgba(0,0,0,0.04),rgba(0,0,0,0.48))]" />
      <div className={["relative min-h-screen lg:grid lg:h-screen", collapsed ? "lg:grid-cols-[92px_1fr]" : "lg:grid-cols-[250px_1fr]"].join(" ")}>
      <aside className="frontoffice-sidebar flex flex-col border-b border-white/10 bg-white/10 text-white backdrop-blur-xl lg:h-screen lg:overflow-hidden lg:border-b-0 lg:border-r">
        <div className={["flex h-16 items-center border-b border-white/10 px-5", collapsed ? "lg:justify-center lg:px-3" : ""].join(" ")}>
          <div className={["flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white text-sm font-semibold text-primary shadow-sm", collapsed ? "" : "mr-3"].join(" ")}>
            LP
          </div>
          <div className={collapsed ? "lg:hidden" : ""}>
            <p className="text-sm font-semibold">LIVE Pulse IA</p>
          </div>
          <button
            onClick={() => setCollapsed((value) => !value)}
            className="ml-auto hidden h-8 w-8 items-center justify-center rounded-md text-white/70 hover:bg-white/10 hover:text-white lg:inline-flex"
            title={collapsed ? "Agrandir le volet" : "Réduire le volet"}
          >
            {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          </button>
        </div>
        <nav className="flex flex-1 gap-1 overflow-x-auto p-3 lg:block lg:overflow-y-auto">
          {(interfaceMode === "simple" ? simpleFrontItems : frontItems).map((item) => {
            const Icon = item.icon;
            const active = "processed" in item && item.processed
              ? pathname === "/opportunities" && searchParams.get("processed") === "true"
              : pathname === item.href && (item.href !== "/opportunities" || (!searchParams.get("status") && !searchParams.get("processed") && !searchParams.get("min_score")));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "flex min-h-10 items-center gap-3 rounded-md px-3 text-sm font-medium hover:bg-white/10",
                  collapsed ? "lg:justify-center lg:px-0" : "",
                  active ? "bg-white text-brand-marine" : "text-white/80"
                ].join(" ")}
                title={item.label}
              >
                <Icon className={["h-4 w-4", active ? "text-primary" : "text-white/70"].join(" ")} />
                <span className={collapsed ? "lg:hidden" : ""}>{item.label}</span>
              </Link>
            );
          })}
          {interfaceMode === "advanced" && <div className={["mt-3 border-t border-white/10 pt-3", collapsed ? "lg:mt-2 lg:pt-2" : ""].join(" ")}>
            <p className={["px-3 pb-2 text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-white/45", collapsed ? "lg:hidden" : ""].join(" ")}>
              Phases AO
            </p>
            <div className="space-y-1">
              {phaseItems.map((item) => {
                const Icon = item.icon;
	                const active =
	                  pathname === "/opportunities" &&
	                  ((item.status && searchParams.get("status") === item.status) ||
                      (item.processed && searchParams.get("processed") === "true"));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={[
                      "flex min-h-9 items-center gap-3 rounded-md px-3 text-xs font-medium hover:bg-white/10",
                      collapsed ? "lg:justify-center lg:px-0" : "",
                      active ? "bg-white text-brand-marine" : "text-white/72"
                    ].join(" ")}
                    title={item.label}
                  >
                    <Icon className={["h-4 w-4", active ? "text-primary" : "text-white/60"].join(" ")} />
                    <span className={collapsed ? "lg:hidden" : ""}>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>}
        </nav>
        <div className="mt-auto space-y-2 border-t border-white/10 p-3">
          {canAccessBackoffice(currentUser) && (
            <Link
              href="/backoffice"
              className={["flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-white/80 hover:bg-white/10", collapsed ? "lg:justify-center lg:px-0" : ""].join(" ")}
              title="Paramètres"
            >
              <LayoutDashboard className="h-4 w-4 text-white/70" />
              <span className={collapsed ? "lg:hidden" : ""}>Paramètres</span>
            </Link>
          )}
          <button
            onClick={onLogout}
            className={["flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-white/80 hover:bg-white/10", collapsed ? "lg:justify-center lg:px-0" : ""].join(" ")}
            title="Déconnexion"
          >
            <LogOut className="h-4 w-4 text-white/70" />
            <span className={collapsed ? "lg:hidden" : ""}>Déconnexion</span>
          </button>
        </div>
      </aside>
      <main className="frontoffice-main min-w-0 lg:h-screen lg:overflow-y-auto">
        <TopBar currentUser={currentUser} interfaceMode={interfaceMode} onInterfaceModeChange={onInterfaceModeChange} />
        {children}
      </main>
      </div>
    </div>
  );
}

function BackofficeShell({
  children,
  currentUser,
  onLogout,
  pathname
}: {
  children: React.ReactNode;
  currentUser: UserProfile | null;
  onLogout: () => void;
  pathname: string;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={["min-h-screen lg:grid lg:h-screen lg:overflow-hidden", collapsed ? "lg:grid-cols-[92px_1fr]" : "lg:grid-cols-[280px_1fr]"].join(" ")}>
      <aside className="flex flex-col border-b border-border bg-brand-marine text-white lg:h-screen lg:overflow-hidden lg:border-b-0 lg:border-r lg:border-brand-marine">
        <div className={["flex h-16 items-center border-b border-white/10 px-5", collapsed ? "lg:justify-center lg:px-3" : ""].join(" ")}>
          <div className={["flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white text-sm font-semibold text-primary shadow-sm", collapsed ? "" : "mr-3"].join(" ")}>
            BO
          </div>
          <div className={collapsed ? "lg:hidden" : ""}>
            <p className="text-sm font-semibold">Backoffice LIVE Pulse IA</p>
            <p className="text-xs text-white/60">Administration et pilotage</p>
          </div>
          <button
            onClick={() => setCollapsed((value) => !value)}
            className="ml-auto hidden h-8 w-8 items-center justify-center rounded-md text-white/70 hover:bg-white/10 hover:text-white lg:inline-flex"
            title={collapsed ? "Agrandir le volet" : "Réduire le volet"}
          >
            {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          </button>
        </div>
        <nav className="flex flex-1 gap-1 overflow-x-auto p-3 lg:block lg:overflow-y-auto">
          {backItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/backoffice" && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "flex min-h-10 items-center gap-3 rounded-md px-3 text-sm font-medium hover:bg-white/10",
                  collapsed ? "lg:justify-center lg:px-0" : "",
                  active ? "bg-white text-brand-marine" : "text-white/80"
                ].join(" ")}
                title={item.label}
              >
                <Icon className={["h-4 w-4", active ? "text-primary" : "text-white/70"].join(" ")} />
                <span className={collapsed ? "lg:hidden" : ""}>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-2 border-t border-white/10 p-3">
          <Link
            href="/frontoffice"
            className={["flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-white/80 hover:bg-white/10", collapsed ? "lg:justify-center lg:px-0" : ""].join(" ")}
            title="Retour au frontoffice"
          >
            <ArrowLeft className="h-4 w-4 text-white/70" />
            <span className={collapsed ? "lg:hidden" : ""}>Retour au frontoffice</span>
          </Link>
          <button
            onClick={onLogout}
            className={["flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-white/80 hover:bg-white/10", collapsed ? "lg:justify-center lg:px-0" : ""].join(" ")}
            title="Déconnexion"
          >
            <LogOut className="h-4 w-4 text-white/70" />
            <span className={collapsed ? "lg:hidden" : ""}>Déconnexion</span>
          </button>
          {currentUser && <p className={["px-3 pt-2 text-xs text-white/50", collapsed ? "lg:hidden" : ""].join(" ")}>{currentUser.email}</p>}
        </div>
      </aside>
      <main className="min-w-0 bg-background lg:h-screen lg:overflow-y-auto">
        <TopBar currentUser={currentUser} variant="back" />
        {children}
      </main>
    </div>
  );
}
