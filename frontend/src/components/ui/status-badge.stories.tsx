import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { expect } from "storybook/test";

import { StatusBadge, type OrderStatus } from "./status-badge";

const meta = {
  title: "UI/Status/StatusBadge",
  component: StatusBadge,
  tags: ["autodocs"],
  argTypes: {
    status: {
      control: "select",
      options: ["pending", "confirmed", "shipped", "delivered", "cancelled"],
    },
  },
} satisfies Meta<typeof StatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Pending: Story = { args: { status: "pending" } };
export const Confirmed: Story = { args: { status: "confirmed" } };
export const Shipped: Story = { args: { status: "shipped" } };
export const Delivered: Story = { args: { status: "delivered" } };
export const Cancelled: Story = { args: { status: "cancelled" } };

const ALL: OrderStatus[] = [
  "pending",
  "confirmed",
  "shipped",
  "delivered",
  "cancelled",
];

/** Every order-lifecycle status together. */
export const AllStatuses: Story = {
  args: { status: "pending" },
  render: () => (
    <div className="flex flex-wrap gap-2">
      {ALL.map((s) => (
        <StatusBadge key={s} status={s} />
      ))}
    </div>
  ),
  play: async ({ canvas }) => {
    await expect(canvas.getByText("Delivered")).toBeVisible();
    await expect(canvas.getByText("Cancelled")).toBeVisible();
  },
};

/** A custom label can override the default status text. */
export const CustomLabel: Story = {
  args: { status: "shipped", label: "In transit" },
};
