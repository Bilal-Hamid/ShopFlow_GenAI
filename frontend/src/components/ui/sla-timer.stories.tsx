import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { expect, fn, waitFor } from "storybook/test";

import { SLATimer } from "./sla-timer";

// Fixed reference instant so frozen stories render deterministically.
const NOW = "2026-07-24T12:00:00Z";

const meta = {
  title: "UI/Status/SLATimer",
  component: SLATimer,
  tags: ["autodocs"],
  args: {
    now: NOW,
    label: "Ship within",
    onExpire: fn(),
  },
} satisfies Meta<typeof SLATimer>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Comfortably ahead of the deadline — green, ~4h remaining. */
export const Healthy: Story = {
  args: { deadline: "2026-07-24T16:00:00Z" },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("04:00:00")).toBeVisible();
  },
};

/** Inside the warn threshold (30 min left) — amber. */
export const Warning: Story = {
  args: { deadline: "2026-07-24T12:30:00Z" },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("00:30:00")).toBeVisible();
  },
};

/** Deadline passed — red "Overdue" and onExpire fires. */
export const Overdue: Story = {
  args: { deadline: "2026-07-24T11:00:00Z" },
  play: async ({ canvas, args }) => {
    await expect(canvas.getByText("Overdue")).toBeVisible();
    await waitFor(() => expect(args.onExpire).toHaveBeenCalledOnce());
  },
};

/** Live countdown with no frozen `now` — ticks every second. */
export const Live: Story = {
  args: { now: undefined, deadline: new Date(Date.now() + 90_000) },
  play: async ({ canvas }) => {
    await expect(canvas.getByRole("timer")).toBeVisible();
  },
};
