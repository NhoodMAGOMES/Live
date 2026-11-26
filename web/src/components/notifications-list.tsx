"use client";

import { Check, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_BASE, getNotifications, type Notification } from "@/lib/api";

export function NotificationsList() {
  const [items, setItems] = useState<Notification[]>([]);

  async function refresh() {
    setItems(await getNotifications());
  }

  useEffect(() => {
    refresh().catch(() => setItems([]));
  }, []);

  async function markRead(id: number) {
    await fetch(`${API_BASE}/notifications/${id}/read`, { method: "PATCH" });
    await refresh();
  }

  return (
    <Card className="front-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border p-4">
        <h2 className="text-sm font-semibold">Notifications</h2>
        <Button onClick={refresh} variant="secondary" size="sm">
          <RefreshCw className="h-4 w-4" />
          Actualiser
        </Button>
      </div>
      <div className="divide-y divide-border">
        {items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <p className="font-medium">{item.title}</p>
                <Badge tone={item.is_read ? "neutral" : "blue"}>{item.is_read ? "Lu" : "Nouveau"}</Badge>
              </div>
              <p className="text-sm text-white/75">{item.message}</p>
              <p className="mt-1 text-xs text-white/60">{new Date(item.created_at).toLocaleString("fr-FR")}</p>
            </div>
            {!item.is_read && (
              <Button onClick={() => markRead(item.id)} variant="secondary" size="sm">
                <Check className="h-4 w-4" />
                Lu
              </Button>
            )}
          </div>
        ))}
        {!items.length && <div className="p-4 text-sm text-white/70">Aucune notification.</div>}
      </div>
    </Card>
  );
}
