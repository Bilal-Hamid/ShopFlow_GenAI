import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

type DrawerSide = "left" | "right" | "top" | "bottom";

interface BaseOverlayProps {
  open: boolean;
  onClose: () => void;
  /** Accessible title; rendered as the heading and wired to aria-labelledby. */
  title?: string;
  /** Extra descriptive text wired to aria-describedby. */
  description?: string;
  /** Close when the backdrop is clicked. @default true */
  closeOnBackdrop?: boolean;
  /** Close when Escape is pressed. @default true */
  closeOnEsc?: boolean;
  children?: React.ReactNode;
  className?: string;
}

/** Duration must match the Tailwind transition classes below. */
const ANIM_MS = 200;

function useDialog(open: boolean, onClose: () => void, closeOnEsc: boolean) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  // Two-phase mount so enter/exit transitions can run.
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (open) {
      // Mount immediately on open; the exit path below delays unmount so the
      // close transition can play. Syncing mount to the `open` prop is the
      // point of this effect.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMounted(true);
      return;
    }
    setVisible(false);
    const t = setTimeout(() => setMounted(false), ANIM_MS);
    return () => clearTimeout(t);
  }, [open]);

  // Once mounted, flip to visible on the next frame to trigger the transition.
  useEffect(() => {
    if (!mounted) return;
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [mounted]);

  // Focus management: capture focus on open, restore on close.
  useEffect(() => {
    if (!mounted) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const node = dialogRef.current;
    const first = node?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? node)?.focus();
    return () => previouslyFocused.current?.focus?.();
  }, [mounted]);

  // Lock body scroll while open.
  useEffect(() => {
    if (!mounted) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mounted]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape" && closeOnEsc) {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      // Trap Tab within the dialog.
      const node = dialogRef.current;
      if (!node) return;
      const focusables = Array.from(
        node.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter((el) => el.offsetParent !== null);
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0]!;
      const last = focusables[focusables.length - 1]!;
      const active = document.activeElement;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    },
    [closeOnEsc, onClose],
  );

  return { dialogRef, mounted, visible, onKeyDown };
}

/** Client-only mount flag so the portal never runs during SSR. */
function useMounted() {
  const [ready, setReady] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setReady(true), []);
  return ready;
}

export interface ModalProps extends BaseOverlayProps {
  /** Max width preset. @default "md" */
  size?: "sm" | "md" | "lg";
}

/** Centered, focus-trapped dialog rendered in a portal. */
export function Modal({
  open,
  onClose,
  title,
  description,
  closeOnBackdrop = true,
  closeOnEsc = true,
  size = "md",
  className,
  children,
}: ModalProps) {
  const ready = useMounted();
  const { dialogRef, mounted, visible, onKeyDown } = useDialog(
    open,
    onClose,
    closeOnEsc,
  );
  const id = useId();
  if (!ready || !mounted) return null;

  const sizes = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" } as const;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onKeyDown={onKeyDown}
    >
      <div
        aria-hidden="true"
        onClick={closeOnBackdrop ? onClose : undefined}
        className={cn(
          "absolute inset-0 bg-black/50 transition-opacity duration-200",
          visible ? "opacity-100" : "opacity-0",
        )}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? `${id}-title` : undefined}
        aria-label={title ? undefined : "Dialog"}
        aria-describedby={description ? `${id}-desc` : undefined}
        tabIndex={-1}
        className={cn(
          "relative w-full rounded-lg border border-border bg-card p-6 text-card-foreground shadow-lg outline-none",
          "transition-all duration-200",
          visible ? "scale-100 opacity-100" : "scale-95 opacity-0",
          sizes[size],
          className,
        )}
      >
        <DialogChrome
          id={id}
          title={title}
          description={description}
          onClose={onClose}
        />
        {children}
      </div>
    </div>,
    document.body,
  );
}

export interface DrawerProps extends BaseOverlayProps {
  /** Edge the drawer slides from. @default "right" */
  side?: DrawerSide;
}

/** Edge-anchored, focus-trapped panel rendered in a portal. */
export function Drawer({
  open,
  onClose,
  title,
  description,
  closeOnBackdrop = true,
  closeOnEsc = true,
  side = "right",
  className,
  children,
}: DrawerProps) {
  const ready = useMounted();
  const { dialogRef, mounted, visible, onKeyDown } = useDialog(
    open,
    onClose,
    closeOnEsc,
  );
  const id = useId();
  if (!ready || !mounted) return null;

  const position: Record<DrawerSide, string> = {
    right: "inset-y-0 right-0 h-full w-full max-w-md border-l",
    left: "inset-y-0 left-0 h-full w-full max-w-md border-r",
    top: "inset-x-0 top-0 w-full max-h-[80vh] border-b",
    bottom: "inset-x-0 bottom-0 w-full max-h-[80vh] border-t",
  };
  const hidden: Record<DrawerSide, string> = {
    right: "translate-x-full",
    left: "-translate-x-full",
    top: "-translate-y-full",
    bottom: "translate-y-full",
  };

  return createPortal(
    <div className="fixed inset-0 z-50" onKeyDown={onKeyDown}>
      <div
        aria-hidden="true"
        onClick={closeOnBackdrop ? onClose : undefined}
        className={cn(
          "absolute inset-0 bg-black/50 transition-opacity duration-200",
          visible ? "opacity-100" : "opacity-0",
        )}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? `${id}-title` : undefined}
        aria-label={title ? undefined : "Drawer"}
        aria-describedby={description ? `${id}-desc` : undefined}
        tabIndex={-1}
        className={cn(
          "absolute overflow-auto border-border bg-card p-6 text-card-foreground shadow-lg outline-none",
          "transition-transform duration-200 ease-out",
          position[side],
          visible ? "translate-x-0 translate-y-0" : hidden[side],
          className,
        )}
      >
        <DialogChrome
          id={id}
          title={title}
          description={description}
          onClose={onClose}
        />
        {children}
      </div>
    </div>,
    document.body,
  );
}

function DialogChrome({
  id,
  title,
  description,
  onClose,
}: {
  id: string;
  title?: string;
  description?: string;
  onClose: () => void;
}) {
  if (!title && !description) {
    return (
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute right-4 top-4 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <CloseIcon />
      </button>
    );
  }
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        {title && (
          <h2 id={`${id}-title`} className="text-lg font-semibold">
            {title}
          </h2>
        )}
        {description && (
          <p id={`${id}-desc`} className="text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="shrink-0 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <CloseIcon />
      </button>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
