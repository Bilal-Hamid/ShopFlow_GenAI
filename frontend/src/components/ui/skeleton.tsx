import { cn } from "@/lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Render as a circle (equal width/height expected via className). */
  circle?: boolean;
}

/**
 * Low-level shimmer placeholder. Compose these to mirror the exact layout of
 * whatever is loading — the design system uses skeletons, never spinners, as
 * the loading fallback for data-fetching components.
 */
export function Skeleton({ circle, className, ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse bg-muted",
        circle ? "rounded-full" : "rounded-md",
        className,
      )}
      {...props}
    />
  );
}

export interface SkeletonTextProps {
  /** Number of lines. @default 3 */
  lines?: number;
  /** Shorten the last line to look like a paragraph tail. @default true */
  lastLineShort?: boolean;
  className?: string;
}

/** A block of placeholder text lines. */
export function SkeletonText({
  lines = 3,
  lastLineShort = true,
  className,
}: SkeletonTextProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            "h-3",
            lastLineShort && i === lines - 1 ? "w-2/3" : "w-full",
          )}
        />
      ))}
    </div>
  );
}
