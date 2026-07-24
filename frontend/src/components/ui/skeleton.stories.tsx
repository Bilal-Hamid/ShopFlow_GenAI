import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { Skeleton, SkeletonText } from "./skeleton";

const meta = {
  title: "UI/Skeleton",
  component: Skeleton,
  tags: ["autodocs"],
} satisfies Meta<typeof Skeleton>;

export default meta;
type Story = StoryObj<typeof meta>;

/** A single placeholder block sized with utility classes. */
export const Default: Story = {
  args: { className: "h-6 w-48" },
};

export const Circle: Story = {
  args: { circle: true, className: "h-12 w-12" },
};

/** Multi-line placeholder text with a shortened tail. */
export const TextLines: StoryObj<typeof SkeletonText> = {
  render: () => <SkeletonText lines={4} className="w-80" />,
};

/**
 * Skeletons should mirror the real layout. This matches the ProductCard:
 * image, title, price row, button.
 */
export const ProductCardShape: Story = {
  render: () => (
    <div
      role="status"
      aria-label="Loading product"
      className="w-64 rounded-lg border border-border p-3"
    >
      <Skeleton className="mb-3 h-40 w-full" />
      <Skeleton className="mb-2 h-4 w-3/4" />
      <div className="mb-3 flex items-center justify-between">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-12" />
      </div>
      <Skeleton className="h-9 w-full" />
      <span className="sr-only">Loading…</span>
    </div>
  ),
};

/** Matches a few rows of a data table. */
export const TableRowsShape: Story = {
  render: () => (
    <div role="status" aria-label="Loading rows" className="w-[28rem]">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-border py-3"
        >
          <Skeleton circle className="h-8 w-8" />
          <Skeleton className="h-3 flex-1" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-12" />
        </div>
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  ),
};
