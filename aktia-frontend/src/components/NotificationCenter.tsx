import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useToasts } from "../context/ToastContext";
import type { NotificationItem } from "../lib/types";

const POLL_INTERVAL_MS = 10_000;

/** Outras telas pedem uma checagem imediata (ex.: logo depois de uma análise). */
export const REFRESH_NOTIFICATIONS_EVENT = "aktia:refresh-notifications";

const osNotificationsSupported = typeof window !== "undefined" && "Notification" in window;

/**
 * Sino de avisos do cabeçalho. Consulta o backend a cada 10 segundos; cada
 * aviso novo vira um alerta no canto da tela e, se o usuário permitiu, uma
 * notificação do sistema operacional, que aparece mesmo com o navegador
 * minimizado ou em outra aba.
 */
export default function NotificationCenter() {
  const { showToast } = useToasts();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [permission, setPermission] = useState(osNotificationsSupported ? Notification.permission : "denied");

  // Avisos já mostrados nesta sessão, para o mesmo aviso não pipocar a cada consulta.
  const announced = useRef<Set<string> | null>(null);

  const markRead = useCallback((id: string) => {
    api
      .markNotificationRead(id)
      .then((list) => {
        setItems(list.items);
        setUnread(list.unread_count);
      })
      .catch(() => undefined);
  }, []);

  const announce = useCallback(
    (item: NotificationItem) => {
      const examPath = item.radiograph_id ? `/radiografias/${item.radiograph_id}?mapa=1` : null;

      showToast({
        key: `notification-${item.id}`,
        tone: "danger",
        title: item.title,
        message: item.message,
        link: examPath ? { to: examPath, label: "Abrir exame" } : undefined,
        action: { label: "Ciente", onClick: () => markRead(item.id) }
      });

      if (osNotificationsSupported && Notification.permission === "granted") {
        const notification = new Notification(item.title, {
          body: item.message,
          tag: item.id,
          requireInteraction: true
        });
        notification.onclick = () => {
          window.focus();
          if (examPath) window.location.assign(examPath);
          notification.close();
        };
      }
    },
    [showToast, markRead]
  );

  const refresh = useCallback(() => {
    api
      .listNotifications()
      .then((list) => {
        setItems(list.items);
        setUnread(list.unread_count);

        const pending = list.items.filter((item) => item.read_at === null);
        if (announced.current === null) {
          // Primeira consulta após abrir o sistema: avisa só o que chegou há
          // pouco, para não despejar avisos antigos de uma vez.
          const recent = Date.now() - 5 * 60_000;
          announced.current = new Set(
            pending.filter((item) => new Date(item.created_at).getTime() < recent).map((item) => item.id)
          );
        }

        for (const item of pending) {
          if (!announced.current.has(item.id)) {
            announced.current.add(item.id);
            announce(item);
          }
        }
      })
      .catch(() => undefined);
  }, [announce]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, POLL_INTERVAL_MS);
    window.addEventListener(REFRESH_NOTIFICATIONS_EVENT, refresh);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener(REFRESH_NOTIFICATIONS_EVENT, refresh);
    };
  }, [refresh]);

  async function enableOsNotifications() {
    if (!osNotificationsSupported) return;
    setPermission(await Notification.requestPermission());
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((current) => !current)}
        aria-label={`Avisos (${unread} não lidos)`}
        className="relative rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Avisos
        {unread > 0 && (
          <span className="absolute -right-2 -top-2 min-w-5 rounded-full bg-red-600 px-1.5 text-center text-xs font-semibold text-white">
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-96 rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-100 p-3">
            <p className="text-sm font-semibold text-slate-700">Avisos</p>
            {osNotificationsSupported && permission === "default" && (
              <button onClick={enableOsNotifications} className="mt-1 text-xs font-medium text-slate-700 underline">
                Ativar avisos fora do sistema (notificações do computador)
              </button>
            )}
            {permission === "granted" && (
              <p className="mt-1 text-xs text-slate-400">
                Avisos fora do sistema ativados. Eles aparecem enquanto o AktIA estiver aberto em alguma aba.
              </p>
            )}
            {osNotificationsSupported && permission === "denied" && (
              <p className="mt-1 text-xs text-slate-400">
                As notificações do computador estão bloqueadas para este site nas configurações do navegador.
              </p>
            )}
          </div>

          {items.length === 0 ? (
            <p className="p-3 text-sm text-slate-400">Nenhum aviso.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
              {items.map((item) => (
                <li key={item.id} className={`p-3 text-sm ${item.read_at ? "" : "bg-red-50"}`}>
                  <p className={`font-medium ${item.read_at ? "text-slate-600" : "text-red-800"}`}>{item.title}</p>
                  <p className="mt-0.5 text-slate-600">{item.message}</p>
                  <div className="mt-2 flex items-center gap-3 text-xs">
                    <span className="text-slate-400">{new Date(item.created_at).toLocaleString("pt-BR")}</span>
                    {item.radiograph_id && (
                      <Link
                        to={`/radiografias/${item.radiograph_id}?mapa=1`}
                        onClick={() => setOpen(false)}
                        className="font-medium text-slate-700 underline"
                      >
                        Abrir exame
                      </Link>
                    )}
                    {item.read_at ? (
                      <span className="text-slate-400">Ciente em {new Date(item.read_at).toLocaleString("pt-BR")}</span>
                    ) : (
                      <button onClick={() => markRead(item.id)} className="font-medium text-slate-700 underline">
                        Ciente
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
