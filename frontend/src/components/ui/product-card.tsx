import { cn } from "@/lib/utils";

import { Button } from "./button";

function StarRow({ className }: { className: string }) {
  return (
    <div className={cn("flex", className)} aria-hidden="true">
      {Array.from({ length: 5 }).map((_, i) => (
        <svg
          key={i}
          className="h-4 w-4"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
        </svg>
      ))}
    </div>
  );
}

function StarRating({ rating }: { rating: number }) {
  const clamped = Math.max(0, Math.min(5, rating));
  const pct = (clamped / 5) * 100;
  return (
    <div
      className="relative inline-block"
      role="img"
      aria-label={`Rated ${clamped} out of 5`}
    >
      <StarRow className="text-muted" />
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ width: `${pct}%` }}
      >
        <StarRow className="text-warning" />
      </div>
    </div>
  );
}

type StockLevel = "in" | "low" | "out";

function stockLevel(stock: number, lowThreshold: number): StockLevel {
  if (stock <= 0) return "out";
  if (stock <= lowThreshold) return "low";
  return "in";
}

const STOCK_META: Record<StockLevel, { label: string; className: string }> = {
  in: {
    label: "In stock",
    className: "bg-success/15 text-success ring-success/30",
  },
  low: {
    label: "Low stock",
    className: "bg-warning/15 text-warning-foreground ring-warning/30",
  },
  out: {
    label: "Out of stock",
    className: "bg-muted text-muted-foreground ring-border",
  },
};

export interface ProductCardProps {
  title: string;
  price: number;
  imageUrl: string;
  imageAlt?: string;
  rating?: number;
  reviewCount?: number;
  stock: number;
  /** At/below this stock count shows "Low stock". @default 5 */
  lowStockThreshold?: number;
  /** ISO 4217 currency for formatting. @default "USD" */
  currency?: string;
  /** Optional link target for the image + title. */
  href?: string;
  onAddToCart?: () => void;
  className?: string;
}

/**
 * Storefront product tile: image, title, price, star rating, a stock badge,
 * and an add-to-cart quick action. Lifts on hover/focus. The image is a plain
 * <img> so the card stays source-agnostic (apps can swap in next/image).
 */
export function ProductCard({
  title,
  price,
  imageUrl,
  imageAlt,
  rating,
  reviewCount,
  stock,
  lowStockThreshold = 5,
  currency = "USD",
  href,
  onAddToCart,
  className,
}: ProductCardProps) {
  const level = stockLevel(stock, lowStockThreshold);
  const meta = STOCK_META[level];
  const outOfStock = level === "out";
  const formattedPrice = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(price);

  const TitleTag = href ? "a" : "span";

  return (
    <div
      className={cn(
        "group flex w-full max-w-64 flex-col overflow-hidden rounded-lg border border-border bg-card text-card-foreground shadow-sm",
        "transition-all duration-200 focus-within:-translate-y-1 focus-within:shadow-md hover:-translate-y-1 hover:shadow-md",
        className,
      )}
    >
      <div className="relative aspect-square overflow-hidden bg-muted">
        <a
          href={href}
          tabIndex={href ? undefined : -1}
          aria-hidden={href ? undefined : true}
          className="block h-full w-full"
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- design-system tile is image-source-agnostic; apps swap in next/image */}
          <img
            src={imageUrl}
            alt={imageAlt ?? title}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        </a>
        <span
          className={cn(
            "absolute left-2 top-2 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
            meta.className,
          )}
        >
          {meta.label}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <TitleTag
          href={href}
          className={cn(
            "line-clamp-2 text-sm font-medium",
            href &&
              "hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          {title}
        </TitleTag>

        {rating != null && (
          <div className="flex items-center gap-1.5">
            <StarRating rating={rating} />
            {reviewCount != null && (
              <span className="text-xs text-muted-foreground">
                ({reviewCount})
              </span>
            )}
          </div>
        )}

        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          <span className="text-base font-semibold">{formattedPrice}</span>
          <Button
            size="sm"
            onClick={onAddToCart}
            disabled={outOfStock}
            aria-label={
              outOfStock ? `${title} is out of stock` : `Add ${title} to cart`
            }
            leftIcon={
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="9" cy="21" r="1" />
                <circle cx="20" cy="21" r="1" />
                <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
              </svg>
            }
          >
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}
