import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { expect, fn, userEvent, waitFor } from "storybook/test";

import {
  MultiSelect,
  Select,
  type SelectOptionGroup,
  type SelectOptions,
} from "./select";

const CATEGORIES: SelectOptions = [
  { label: "Ceramics", value: "ceramics" },
  { label: "Textiles", value: "textiles" },
  { label: "Woodwork", value: "woodwork" },
  { label: "Jewelry", value: "jewelry" },
  { label: "Candles", value: "candles" },
];

const GROUPED: SelectOptionGroup[] = [
  {
    label: "Home",
    options: [
      { label: "Ceramics", value: "ceramics" },
      { label: "Candles", value: "candles" },
      { label: "Rugs", value: "rugs", disabled: true },
    ],
  },
  {
    label: "Wearables",
    options: [
      { label: "Textiles", value: "textiles" },
      { label: "Jewelry", value: "jewelry" },
    ],
  },
];

const meta = {
  title: "UI/Select",
  component: Select,
  tags: ["autodocs"],
  args: {
    options: CATEGORIES,
    label: "Category",
    placeholder: "Choose a category",
    onChange: fn(),
  },
  parameters: { layout: "padded" },
} satisfies Meta<typeof Select>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Single-select. Opening reveals the listbox; picking closes it. */
export const Default: Story = {
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("combobox"));
    await expect(canvas.getByRole("listbox")).toBeVisible();
    await userEvent.click(canvas.getByRole("option", { name: "Woodwork" }));
    await expect(canvas.getByRole("combobox")).toHaveTextContent("Woodwork");
  },
};

/** Typing in the search box filters the visible options. */
export const Searchable: Story = {
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("combobox"));
    await userEvent.type(canvas.getByRole("searchbox"), "cera");
    await expect(
      canvas.getByRole("option", { name: "Ceramics" }),
    ).toBeVisible();
    await expect(
      canvas.queryByRole("option", { name: "Textiles" }),
    ).not.toBeInTheDocument();
  },
};

export const Grouped: Story = {
  args: { options: GROUPED },
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("combobox"));
    await expect(canvas.getByText("Home")).toBeVisible();
    await expect(canvas.getByText("Wearables")).toBeVisible();
    // Disabled option cannot be chosen (force past pointer-events:none).
    await userEvent.click(canvas.getByRole("option", { name: "Rugs" }), {
      pointerEventsCheck: 0,
    });
    await expect(canvas.getByRole("combobox")).toHaveTextContent(
      "Choose a category",
    );
  },
};

/** Multiple selection renders removable chips. */
export const Multiple: StoryObj<typeof MultiSelect> = {
  render: (args) => (
    <MultiSelect
      options={CATEGORIES}
      label="Categories"
      placeholder="Choose categories"
      onChange={args.onChange}
    />
  ),
  args: { onChange: fn(), options: CATEGORIES },
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("combobox"));
    await userEvent.click(canvas.getByRole("option", { name: "Ceramics" }));
    await userEvent.click(canvas.getByRole("option", { name: "Jewelry" }));
    const trigger = canvas.getByRole("combobox");
    await expect(trigger).toHaveTextContent("Ceramics");
    await expect(trigger).toHaveTextContent("Jewelry");
    // Remove one chip.
    await userEvent.click(
      canvas.getByRole("button", { name: "Remove Ceramics" }),
    );
    await expect(trigger).not.toHaveTextContent("Ceramics");
  },
};

/** Async option loading: options are fetched (debounced) after opening. */
export const AsyncLoading: Story = {
  args: {
    options: [],
    label: "Search catalog",
    placeholder: "Type to search products",
    loadOptions: async (query: string) => {
      await new Promise((r) => setTimeout(r, 150));
      const all: SelectOptions = [
        { label: "Ceramic Mug", value: "mug" },
        { label: "Ceramic Bowl", value: "bowl" },
        { label: "Wool Scarf", value: "scarf" },
        { label: "Oak Cutting Board", value: "board" },
      ];
      return query
        ? (all as { label: string; value: string }[]).filter((o) =>
            o.label.toLowerCase().includes(query.toLowerCase()),
          )
        : all;
    },
  },
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("combobox"));
    await expect(canvas.getByText("Loading…")).toBeVisible();
    await waitFor(() =>
      expect(canvas.getByRole("option", { name: "Ceramic Mug" })).toBeVisible(),
    );
  },
};

export const WithError: Story = {
  args: { error: "Please choose a category." },
};

export const Disabled: Story = {
  args: { disabled: true, defaultValue: "ceramics" },
  play: async ({ canvas }) => {
    await expect(canvas.getByRole("combobox")).toBeDisabled();
  },
};

/** Controlled single-select wired to external state. */
export const Controlled: Story = {
  render: (args) => {
    const ControlledSelect = () => {
      const [value, setValue] = useState<string | string[]>("textiles");
      return (
        <div className="flex flex-col gap-2">
          <Select {...args} value={value} onChange={(v) => setValue(v)} />
          <p className="text-xs text-muted-foreground">
            Selected: {String(value) || "none"}
          </p>
        </div>
      );
    };
    return <ControlledSelect />;
  },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("Selected: textiles")).toBeInTheDocument();
    await userEvent.click(canvas.getByRole("combobox"));
    await userEvent.click(canvas.getByRole("option", { name: "Candles" }));
    await expect(canvas.getByText("Selected: candles")).toBeInTheDocument();
  },
};
