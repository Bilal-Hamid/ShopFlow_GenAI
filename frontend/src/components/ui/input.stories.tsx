import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { expect, fn, userEvent } from "storybook/test";

import { Input, Textarea } from "./input";

const meta = {
  title: "UI/Input",
  component: Input,
  tags: ["autodocs"],
  args: {
    label: "Email",
    placeholder: "you@example.com",
    onChange: fn(),
  },
} satisfies Meta<typeof Input>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithHelperText: Story = {
  args: {
    label: "Store name",
    placeholder: "Acme Goods",
    helperText: "This is shown to customers on your storefront.",
  },
};

/** Error message replaces helper text and drives aria-invalid. */
export const WithError: Story = {
  args: {
    label: "Email",
    value: "not-an-email",
    error: "Enter a valid email address.",
  },
  play: async ({ canvas }) => {
    const input = canvas.getByLabelText("Email");
    await expect(input).toHaveAttribute("aria-invalid", "true");
    await expect(
      canvas.getByText("Enter a valid email address."),
    ).toBeVisible();
  },
};

export const Required: Story = {
  args: { label: "Password", type: "password", required: true },
};

export const Disabled: Story = {
  args: { label: "Email", value: "locked@example.com", disabled: true },
  play: async ({ canvas }) => {
    const input = canvas.getByLabelText("Email");
    await expect(input).toBeDisabled();
    // Label is greyed to reinforce the disabled state.
    await expect(canvas.getByText("Email")).toHaveClass(
      "text-muted-foreground",
    );
  },
};

/** Uncontrolled input with a live character counter. */
export const WithCharacterCount: Story = {
  args: {
    label: "Coupon code",
    defaultValue: "SAVE10",
    maxLength: 12,
    showCount: true,
  },
  play: async ({ canvas }) => {
    const input = canvas.getByLabelText("Coupon code");
    await expect(canvas.getByText("6/12")).toBeInTheDocument();
    await userEvent.type(input, "OFF");
    await expect(canvas.getByText("9/12")).toBeInTheDocument();
  },
};

/** Controlled usage: parent owns the value; typing updates it and the count. */
export const Controlled: Story = {
  render: (args) => {
    const ControlledInput = () => {
      const [value, setValue] = useState("");
      return (
        <div className="flex flex-col gap-2">
          <Input
            {...args}
            label="Search products"
            value={value}
            maxLength={40}
            showCount
            onChange={(e) => setValue(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">Value: {value}</p>
        </div>
      );
    };
    return <ControlledInput />;
  },
  play: async ({ canvas }) => {
    await userEvent.type(canvas.getByLabelText("Search products"), "mug");
    await expect(canvas.getByText("Value: mug")).toBeInTheDocument();
    await expect(canvas.getByText("3/40")).toBeInTheDocument();
  },
};

/** The Textarea shares the same field frame (label, error, helper, count). */
export const TextareaDefault: StoryObj<typeof Textarea> = {
  render: () => (
    <Textarea
      label="Product description"
      placeholder="Describe your handmade product…"
      helperText="Markdown is not supported here."
      maxLength={200}
      showCount
      defaultValue="A hand-thrown ceramic mug."
    />
  ),
};
