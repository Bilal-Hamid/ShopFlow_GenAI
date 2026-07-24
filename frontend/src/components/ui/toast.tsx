"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** Auto-dismiss delay in ms. Pass 0 to disable auto-dismiss. @default 5000 */
  duration?: number;
}

interface ToastRecord extends Required<Omit<ToastOptions, "description">> {
  id: number;
  description?: string;
}

interface ToastContextValue {
  toast: (opts: ToastOptions) => number;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a <ToastProvider>");
  return ctx;
}

const VARIANT_META: Record<
  ToastVariant,
  {
    accent: string;
    bar: string;
    icon: React.ReactNode;
    role: "status" | "alert";
  }
> = {
  success: {
    accent: "border-l-success text-success",
    bar: "bg-success",
    role: "status",
    icon: <path d="M20 6 9 17l-5-5" />,
  },
  error: {
    accent: "border-l-destructive text-destructive",
    bar: "bg-destructive",
    role: "alert",
    icon: (
      <>
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </>
    ),
  },
  warning: {
    accent: "border-l-warning text-warning-foreground",
    bar: "bg-warning",
    role: "alert",
    icon: (
      <>
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </>
    ),
  },
  info: {
    accent: "border-l-primary text-primary",
    bar: "bg-primary",
    role: "status",
    icon: (
      <>
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </>
    ),
  },
};

export interface ToastProviderProps {
  children: React.ReactNode;
  /** Max toasts shown at once; the rest queue until a slot frees. @default 3 */
  limit?: number;
}

export function ToastProvider({ children, limit = 3 }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((opts: ToastOptions) => {
    const id = (idRef.current += 1);
    setToasts((prev) => [
      ...prev,
      {
        id,
        title: opts.title,
        description: opts.description,
        variant: opts.variant ?? "info",
        duration: opts.duration ?? 5000,
      },
    ]);
    return id;
  }, []);

  const value = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);
  // Queue management: only the first `limit` are live; the rest wait.
  const visible = toasts.slice(0, limit);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={visible} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastRecord[];
  onDismiss: (id: number) => void;
}) {
  const [mounted, setMounted] = useState(false);
  // Client-only mount flag so the portal never runs during SSR.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return createPortal(
    <div
      role="region"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-0 right-0 z-[100] flex w-full max-w-sm flex-col gap-2 p-4"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>,
    document.body,
  );
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastRecord;
  onDismiss: (id: number) => void;
}) {
  const meta = VARIANT_META[toast.variant];
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (toast.duration <= 0) return;
    // Kick the progress bar from 100% -> 0% over the duration, then dismiss.
    const raf = requestAnimationFrame(() => setProgress(0));
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      role={meta.role}
      aria-atomic="true"
      className={cn(
        "pointer-events-auto relative overflow-hidden rounded-md border border-l-4 bg-card p-4 pr-9 text-card-foreground shadow-lg",
        meta.accent,
      )}
    >
      <div className="flex items-start gap-3">
        <svg
          className={cn("mt-0.5 h-5 w-5 shrink-0", meta.accent)}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          {meta.icon}
        </svg>
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-medium">{toast.title}</p>
          {toast.description && (
            <p className="text-sm text-muted-foreground">{toast.description}</p>
          )}
        </div>
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(toast.id)}
        className="absolute right-2 top-2 rounded-sm p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <svg
          className="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
      {toast.duration > 0 && (
        <div
          aria-hidden="true"
          className={cn("absolute bottom-0 left-0 h-1", meta.bar)}
          style={{
            width: `${progress}%`,
            transition: `width ${toast.duration}ms linear`,
          }}
        />
      )}
    </div>
  );
}
