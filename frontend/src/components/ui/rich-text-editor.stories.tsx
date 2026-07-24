import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { expect, fn, userEvent, waitFor } from "storybook/test";

import { RichTextEditor } from "./rich-text-editor";

const meta = {
  title: "UI/RichTextEditor",
  component: RichTextEditor,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
  args: {
    label: "Product description",
    defaultValue: "<p>A hand-thrown ceramic mug, glazed in matte blue.</p>",
    onChange: fn(),
  },
} satisfies Meta<typeof RichTextEditor>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  play: async ({ canvas }) => {
    await expect(
      canvas.getByRole("toolbar", { name: "Formatting" }),
    ).toBeVisible();
    await expect(
      canvas.getByText(/hand-thrown ceramic mug/),
    ).toBeInTheDocument();
  },
};

/** The Bold toggle reflects its active state via aria-pressed. */
export const ToggleBold: Story = {
  play: async ({ canvas }) => {
    const bold = canvas.getByRole("button", { name: "Bold" });
    await expect(bold).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(bold);
    await waitFor(() => expect(bold).toHaveAttribute("aria-pressed", "true"));
    await userEvent.click(bold);
    await waitFor(() => expect(bold).toHaveAttribute("aria-pressed", "false"));
  },
};

/** Typing in the editor emits updated HTML via onChange. */
export const EmitsHtmlOnType: Story = {
  args: { defaultValue: "<p>Start</p>" },
  play: async ({ canvas, args }) => {
    const editor = canvas.getByRole("textbox");
    await userEvent.click(editor);
    await userEvent.type(editor, " more");
    await waitFor(() => expect(args.onChange).toHaveBeenCalled());
  },
};

/** The link button reveals an inline URL input. */
export const LinkInput: Story = {
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: "Link" }));
    await expect(canvas.getByLabelText("Link URL")).toBeVisible();
  },
};

export const Empty: Story = {
  args: {
    defaultValue: "",
    helperText: "Supports bold, italic, lists, and links.",
  },
};

/** Disabled state: toolbar controls are inert and the textbox is read-only. */
export const Disabled: Story = {
  args: { disabled: true },
  play: async ({ canvas }) => {
    await expect(canvas.getByRole("button", { name: "Bold" })).toBeDisabled();
  },
};

export const WithError: Story = {
  args: { error: "Description is required.", defaultValue: "" },
};
