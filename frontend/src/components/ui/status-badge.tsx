import { cn } from "@/lib/utils";

/** Mirrors the backend `OrderStatus` enum (app/models/order.py). */
export type OrderStatus =
  "pending" | "confirmed" | "shipped" | "delivered" | "cancelled";

interface StatusMeta {
  label: string;
  /** Tailwind classes for the badge surface + dot. */
  surface: string;
  dot: string;
  /** Active states get a pulsing dot to signal work in progress. */
  pulse: boolean;
}

const STATUS_META: Record<OrderStatus, StatusMeta> = {
  pending: {
    label: "Pending",
    surface: "bg-warning/15 text-warning-foreground ring-warning/30",
    dot: "bg-warning",
    pulse: true,
  },
  confirmed: {
    label: "Confirmed",
    surface: "bg-primary/15 text-primary ring-primary/30",
    dot: "bg-primary",
    pulse: false,
  },
  shipped: {
    label: "Shipped",
    surface: "bg-accent text-accent-foreground ring-border",
    dot: "bg-foreground/60",
    pulse: true,
  },
  delivered: {
    label: "Delivered",
    surface: "bg-success/15 text-success ring-success/30",
    dot: "bg-success",
    pulse: false,
  },
  cancelled: {
    label: "Cancelled",
    surface: "bg-destructive/15 text-destructive ring-destructive/30",
    dot: "bg-destructive",
    pulse: false,
  },
};

export interface StatusBadgeProps {
  status: OrderStatus;
  /** Override the default human label. */
  label?: string;
  className?: string;
}

/**
 * Colour-coded pill for an order's lifecycle status. Colours map to the
 * backend order-status enum; in-progress states (pending, shipped) show a
 * pulsing dot.
 */
export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const meta = STATUS_META[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        meta.surface,
        className,
      )}
    >
      <span className="relative flex h-2 w-2" aria-hidden="true">
        {meta.pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              meta.dot,
            )}
          />
        )}
        <span
          className={cn("relative inline-flex h-2 w-2 rounded-full", meta.dot)}
        />
      </span>
      {label ?? meta.label}
    </span>
  );
}
