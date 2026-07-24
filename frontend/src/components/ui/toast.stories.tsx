import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";

import { Button } from "./button";
import { ToastProvider, useToast, type ToastVariant } from "./toast";

const body = () => within(document.body);

function Triggers({ duration }: { duration?: number }) {
  const { toast } = useToast();
  const variants: ToastVariant[] = ["success", "error", "warning", "info"];
  const copy: Record<ToastVariant, string> = {
    success: "Order placed successfully",
    error: "Payment failed",
    warning: "Only 2 items left in stock",
    info: "Your cart was saved",
  };
  return (
    <div className="flex flex-wrap gap-2">
      {variants.map((v) => (
        <Button
          key={v}
          variant={v === "error" ? "danger" : "secondary"}
          onClick={() =>
            toast({
              variant: v,
              title: copy[v],
              description: `(${v})`,
              duration,
            })
          }
        >
          Show {v}
        </Button>
      ))}
    </div>
  );
}

const meta = {
  title: "UI/Toast",
  component: ToastProvider,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
  // Each story provides its own children via `render`; placeholder for types.
  args: { children: null },
} satisfies Meta<typeof ToastProvider>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Trigger any of the four variants; each auto-dismisses with a progress bar. */
export const Playground: Story = {
  render: () => (
    <ToastProvider>
      <Triggers />
    </ToastProvider>
  ),
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Show success" }));
    await expect(
      await body().findByText("Order placed successfully"),
    ).toBeVisible();
  },
};

/** All four variants shown at once (persistent) for visual + a11y coverage. */
export const AllVariants: Story = {
  render: () => (
    <ToastProvider limit={4}>
      <Triggers duration={0} />
    </ToastProvider>
  ),
  play: async ({ canvas }) => {
    for (const v of ["success", "error", "warning", "info"]) {
      await userEvent.click(canvas.getByRole("button", { name: `Show ${v}` }));
    }
    await expect(
      await body().findByText("Only 2 items left in stock"),
    ).toBeVisible();
  },
};

/** Error and warning use role="alert"; success/info use role="status". */
export const AlertVariant: Story = {
  render: () => (
    <ToastProvider>
      <Triggers duration={0} />
    </ToastProvider>
  ),
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Show error" }));
    const alert = await body().findByRole("alert");
    await expect(alert).toHaveTextContent("Payment failed");
  },
};

/** Close button removes a toast immediately. */
export const ManualDismiss: Story = {
  render: () => (
    <ToastProvider>
      <Triggers duration={0} />
    </ToastProvider>
  ),
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Show info" }));
    await body().findByText("Your cart was saved");
    await userEvent.click(
      body().getByRole("button", { name: "Dismiss notification" }),
    );
    await waitFor(() =>
      expect(body().queryByText("Your cart was saved")).not.toBeInTheDocument(),
    );
  },
};

/** With limit=2, only two toasts show at once; the rest queue. */
export const QueueManagement: Story = {
  render: () => (
    <ToastProvider limit={2}>
      <QueueTrigger />
    </ToastProvider>
  ),
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Enqueue 4" }));
    await waitFor(() => expect(body().getAllByRole("status")).toHaveLength(2));
  },
};

function QueueTrigger() {
  const { toast } = useToast();
  return (
    <Button
      onClick={() => {
        for (let i = 1; i <= 4; i++) {
          toast({ variant: "info", title: `Notification ${i}`, duration: 0 });
        }
      }}
    >
      Enqueue 4
    </Button>
  );
}
