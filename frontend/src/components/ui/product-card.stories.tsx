import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { expect, fn, userEvent } from "storybook/test";

import { ProductCard } from "./product-card";

// Inline SVG data URI keeps stories/tests hermetic (no network image).
const placeholder = (label: string) =>
  `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="100%" height="100%" fill="#e2e8f0"/><text x="50%" y="50%" font-family="sans-serif" font-size="28" fill="#64748b" text-anchor="middle" dominant-baseline="middle">${label}</text></svg>`,
  )}`;

const meta = {
  title: "UI/ProductCard",
  component: ProductCard,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
  args: {
    title: "Hand-thrown Ceramic Mug",
    price: 24,
    imageUrl: placeholder("Mug"),
    rating: 4.5,
    reviewCount: 128,
    stock: 42,
    onAddToCart: fn(),
  },
} satisfies Meta<typeof ProductCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  play: async ({ canvas, args }) => {
    await expect(canvas.getByText("$24.00")).toBeVisible();
    await expect(
      canvas.getByRole("img", { name: "Rated 4.5 out of 5" }),
    ).toBeVisible();
    await userEvent.click(
      canvas.getByRole("button", { name: /Add .* to cart/ }),
    );
    await expect(args.onAddToCart).toHaveBeenCalledOnce();
  },
};

export const LowStock: Story = {
  args: {
    title: "Silver Hoop Earrings",
    price: 89,
    imageUrl: placeholder("Rings"),
    stock: 3,
    rating: 5,
  },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("Low stock")).toBeVisible();
  },
};

/** Out of stock disables the add-to-cart action. */
export const OutOfStock: Story = {
  args: {
    title: "Oak Cutting Board",
    price: 52,
    imageUrl: placeholder("Board"),
    stock: 0,
    rating: 4,
  },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("Out of stock")).toBeVisible();
    await expect(
      canvas.getByRole("button", { name: /out of stock/ }),
    ).toBeDisabled();
  },
};

/** Title and image link out when `href` is provided. */
export const WithLink: Story = {
  args: {
    href: "#product",
    title: "Wool Throw Blanket",
    imageUrl: placeholder("Throw"),
  },
};

export const NoRating: Story = {
  args: {
    rating: undefined,
    reviewCount: undefined,
    title: "Beeswax Candle Set",
    imageUrl: placeholder("Candles"),
  },
};

/** A responsive grid of cards. */
export const Grid: Story = {
  render: (args) => (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
      <ProductCard
        {...args}
        title="Ceramic Mug"
        imageUrl={placeholder("Mug")}
        stock={42}
        rating={4.5}
      />
      <ProductCard
        {...args}
        title="Wool Scarf"
        imageUrl={placeholder("Scarf")}
        stock={4}
        rating={4}
        price={35}
      />
      <ProductCard
        {...args}
        title="Oak Board"
        imageUrl={placeholder("Board")}
        stock={0}
        rating={3.5}
        price={52}
      />
    </div>
  ),
};
