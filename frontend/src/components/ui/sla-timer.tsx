import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface SLATimerProps {
  /** Target deadline. */
  deadline: Date | string | number;
  /**
   * Reference "current time". Defaults to the live clock (ticks every second).
   * Pass a fixed value to freeze the timer — used by stories/tests for
   * deterministic rendering.
   */
  now?: Date | string | number;
  /** Remaining time at/under which the timer turns amber (ms). @default 3600000 (1h) */
  warnThresholdMs?: number;
  /** Optional caption shown above the countdown. */
  label?: string;
  /** Called once when the deadline is first reached. */
  onExpire?: () => void;
  className?: string;
}

function toMs(value: Date | string | number): number {
  return value instanceof Date ? value.getTime() : new Date(value).getTime();
}

function format(remainingMs: number): string {
  const total = Math.max(0, Math.floor(remainingMs / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

/**
 * Animated countdown to an SLA deadline. Renders healthy (foreground),
 * warning (amber) as the deadline nears, and overdue (red) once passed.
 * Live by default; pass `now` to freeze it deterministically.
 */
export function SLATimer({
  deadline,
  now,
  warnThresholdMs = 60 * 60 * 1000,
  label,
  onExpire,
  className,
}: SLATimerProps) {
  const frozen = now != null;
  const deadlineMs = toMs(deadline);

  // Only the live case needs state; the frozen value is derived during render.
  const [liveNowMs, setLiveNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (frozen) return;
    const id = setInterval(() => setLiveNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [frozen]);

  const nowMs = frozen ? toMs(now) : liveNowMs;
  const remaining = deadlineMs - nowMs;
  const isExpired = remaining <= 0;
  const isWarning = !isExpired && remaining <= warnThresholdMs;

  // Fire onExpire exactly once per crossing; a ref avoids a render-triggering
  // setState inside the effect.
  const expiredFiredRef = useRef(false);
  useEffect(() => {
    if (isExpired && !expiredFiredRef.current) {
      expiredFiredRef.current = true;
      onExpire?.();
    } else if (!isExpired) {
      expiredFiredRef.current = false;
    }
  }, [isExpired, onExpire]);

  const tone = isExpired
    ? "text-destructive"
    : isWarning
      ? "text-warning-foreground"
      : "text-foreground";
  const dotTone = isExpired
    ? "bg-destructive"
    : isWarning
      ? "bg-warning"
      : "bg-success";

  return (
    <div
      role="timer"
      aria-live={frozen ? "off" : "polite"}
      aria-label={label ?? "Time remaining"}
      className={cn("inline-flex items-center gap-2", className)}
    >
      <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
        {!isExpired && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              dotTone,
            )}
          />
        )}
        <span
          className={cn(
            "relative inline-flex h-2.5 w-2.5 rounded-full",
            dotTone,
          )}
        />
      </span>
      <span className="flex flex-col leading-tight">
        {label && (
          <span className="text-xs text-muted-foreground">{label}</span>
        )}
        <span
          className={cn("font-mono text-sm font-semibold tabular-nums", tone)}
        >
          {isExpired ? "Overdue" : format(remaining)}
        </span>
      </span>
    </div>
  );
}
