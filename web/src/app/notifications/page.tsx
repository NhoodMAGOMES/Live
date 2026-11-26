import { Bell, Sparkles } from "lucide-react";

import { NotificationsList } from "@/components/notifications-list";

export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <section className="mb-5 rounded-lg border border-white/20 bg-white/20 p-5 text-white shadow-2xl backdrop-blur-xl sm:p-6">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold uppercase text-white/80">
          <Sparkles className="h-3.5 w-3.5 text-brand-gold" />
          Signaux métier
        </div>
        <div className="flex items-center gap-3">
          <Bell className="h-6 w-6 text-brand-gold" />
          <div>
            <h1 className="text-3xl font-semibold leading-tight">Notifications</h1>
            <p className="mt-2 text-sm text-white/75">AO détectés, scores seuils, deadlines et erreurs connecteurs.</p>
          </div>
        </div>
      </section>
      <NotificationsList />
    </div>
  );
}
