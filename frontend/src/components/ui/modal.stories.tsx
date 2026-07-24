import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { expect, fn, userEvent, waitFor, within } from "storybook/test";

import { Button } from "./button";
import { Drawer, Modal } from "./modal";

const meta = {
  title: "UI/Modal",
  component: Modal,
  tags: ["autodocs"],
  parameters: { layout: "centered" },
  // Stories drive open/close via their own state, so these are placeholders
  // that satisfy the required props on the meta.
  args: { open: false, onClose: () => {} },
} satisfies Meta<typeof Modal>;

export default meta;
type Story = StoryObj<typeof meta>;

// Portal content lands on document.body, outside the story canvas.
const body = () => within(document.body);

function ModalDemo({
  onClose,
  ...props
}: Partial<React.ComponentProps<typeof Modal>> & { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open modal</Button>
      <Modal
        open={open}
        onClose={() => {
          setOpen(false);
          onClose?.();
        }}
        title="Confirm checkout"
        description="Review your order before placing it."
        {...props}
      >
        <p className="mb-4 text-sm">
          Your cart total is <strong>$48.00</strong>.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={() => setOpen(false)}>Place order</Button>
        </div>
      </Modal>
    </>
  );
}

export const Default: Story = {
  render: () => <ModalDemo />,
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Open modal" }));
    const dialog = await body().findByRole("dialog");
    // Wait out the enter transition before asserting visibility.
    await waitFor(() => expect(dialog).toBeVisible());
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await userEvent.click(body().getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(body().queryByRole("dialog")).not.toBeInTheDocument(),
    );
  },
};

/** Focus moves into the dialog on open (focus trap entry). */
export const FocusMovesIn: Story = {
  render: () => <ModalDemo />,
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Open modal" }));
    const dialog = await body().findByRole("dialog");
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );
  },
};

/** Escape closes the dialog. */
export const EscToClose: Story = {
  render: () => <ModalDemo />,
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Open modal" }));
    await body().findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() =>
      expect(body().queryByRole("dialog")).not.toBeInTheDocument(),
    );
  },
};

/** Clicking the backdrop closes the dialog. */
export const BackdropClick: Story = {
  render: () => <ModalDemo />,
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Open modal" }));
    const dialog = await body().findByRole("dialog");
    const backdrop = dialog.previousElementSibling as HTMLElement;
    await userEvent.click(backdrop);
    await waitFor(() =>
      expect(body().queryByRole("dialog")).not.toBeInTheDocument(),
    );
  },
};

/** With closeOnBackdrop disabled, backdrop clicks are ignored. */
export const PersistentBackdrop: Story = {
  render: () => <ModalDemo closeOnBackdrop={false} onClose={fn()} />,
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Open modal" }));
    const dialog = await body().findByRole("dialog");
    const backdrop = dialog.previousElementSibling as HTMLElement;
    await userEvent.click(backdrop);
    // Still open — closeOnBackdrop is disabled.
    await expect(body().getByRole("dialog")).toBeInTheDocument();
  },
};

function DrawerDemo(props: Partial<React.ComponentProps<typeof Drawer>>) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open drawer</Button>
      <Drawer
        open={open}
        onClose={() => setOpen(false)}
        title="Order details"
        description="Order #10482"
        {...props}
      >
        <p className="text-sm">Status timeline and line items go here.</p>
      </Drawer>
    </>
  );
}

export const DrawerRight: StoryObj<typeof Drawer> = {
  args: { open: false, onClose: () => {} },
  render: () => <DrawerDemo side="right" />,
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Open drawer" }));
    await expect(await body().findByRole("dialog")).toBeVisible();
    await userEvent.click(body().getByRole("button", { name: "Close" }));
    await waitFor(() =>
      expect(body().queryByRole("dialog")).not.toBeInTheDocument(),
    );
  },
};

export const DrawerBottom: StoryObj<typeof Drawer> = {
  args: { open: false, onClose: () => {} },
  render: () => <DrawerDemo side="bottom" />,
};
