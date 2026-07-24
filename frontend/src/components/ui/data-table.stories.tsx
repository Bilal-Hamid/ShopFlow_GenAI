import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { expect, fn, userEvent, waitFor } from "storybook/test";

import { StatusBadge, type OrderStatus } from "./status-badge";
import { DataTable, type DataTableColumn } from "./data-table";

interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  stock: number;
  status: OrderStatus;
}

const PRODUCTS: Product[] = [
  {
    id: "p1",
    name: "Ceramic Mug",
    category: "Ceramics",
    price: 18,
    stock: 42,
    status: "delivered",
  },
  {
    id: "p2",
    name: "Wool Scarf",
    category: "Textiles",
    price: 35,
    stock: 12,
    status: "shipped",
  },
  {
    id: "p3",
    name: "Oak Board",
    category: "Woodwork",
    price: 52,
    stock: 0,
    status: "cancelled",
  },
  {
    id: "p4",
    name: "Silver Ring",
    category: "Jewelry",
    price: 89,
    stock: 7,
    status: "confirmed",
  },
  {
    id: "p5",
    name: "Soy Candle",
    category: "Candles",
    price: 12,
    stock: 120,
    status: "pending",
  },
  {
    id: "p6",
    name: "Linen Napkins",
    category: "Textiles",
    price: 24,
    stock: 30,
    status: "delivered",
  },
  {
    id: "p7",
    name: "Clay Bowl",
    category: "Ceramics",
    price: 28,
    stock: 5,
    status: "shipped",
  },
  {
    id: "p8",
    name: "Walnut Spoon",
    category: "Woodwork",
    price: 9,
    stock: 60,
    status: "delivered",
  },
  {
    id: "p9",
    name: "Gold Studs",
    category: "Jewelry",
    price: 140,
    stock: 3,
    status: "confirmed",
  },
  {
    id: "p10",
    name: "Beeswax Set",
    category: "Candles",
    price: 22,
    stock: 18,
    status: "pending",
  },
  {
    id: "p11",
    name: "Cotton Throw",
    category: "Textiles",
    price: 45,
    stock: 9,
    status: "shipped",
  },
  {
    id: "p12",
    name: "Teak Tray",
    category: "Woodwork",
    price: 38,
    stock: 14,
    status: "delivered",
  },
];

const columns: DataTableColumn<Product>[] = [
  {
    key: "name",
    header: "Product",
    accessor: (r) => r.name,
    sortable: true,
    sortValue: (r) => r.name,
  },
  {
    key: "category",
    header: "Category",
    accessor: (r) => r.category,
    sortable: true,
    sortValue: (r) => r.category,
  },
  {
    key: "price",
    header: "Price",
    accessor: (r) => `$${r.price.toFixed(2)}`,
    sortable: true,
    sortValue: (r) => r.price,
  },
  {
    key: "stock",
    header: "Stock",
    accessor: (r) => r.stock,
    sortable: true,
    sortValue: (r) => r.stock,
  },
  {
    key: "status",
    header: "Status",
    accessor: (r) => <StatusBadge status={r.status} />,
    sortValue: (r) => r.status,
  },
];

const meta = {
  title: "UI/DataTable",
  component: DataTable,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
  args: {
    columns,
    data: PRODUCTS,
    getRowId: (r: Product) => r.id,
    caption: "Product inventory",
  },
} satisfies Meta<typeof DataTable<Product>>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  play: async ({ canvas }) => {
    await expect(
      canvas.getByRole("columnheader", { name: /Product/ }),
    ).toBeVisible();
    await expect(canvas.getByText("Ceramic Mug")).toBeVisible();
  },
};

/** Clicking a sortable header sorts ascending, then descending. */
export const Sorting: Story = {
  args: { pageSize: 20 },
  play: async ({ canvas }) => {
    await userEvent.click(canvas.getByRole("button", { name: /Price/ }));
    const header = canvas.getByRole("columnheader", { name: /Price/ });
    await expect(header).toHaveAttribute("aria-sort", "ascending");
    // Cheapest product ($9 Walnut Spoon) should now be first.
    const rows = canvas.getAllByRole("row");
    // rows[0] is the header row; rows[1] is the first data row.
    await expect(rows[1]).toHaveTextContent("Walnut Spoon");
  },
};

/** Row selection reports the count and fires onSelectionChange. */
export const Selectable: Story = {
  args: { selectable: true, onSelectionChange: fn(), pageSize: 20 },
  play: async ({ canvas, args }) => {
    await userEvent.click(
      canvas.getByRole("checkbox", { name: "Select row p1" }),
    );
    await userEvent.click(
      canvas.getByRole("checkbox", { name: "Select row p2" }),
    );
    await expect(canvas.getByText(/2 selected/)).toBeVisible();
    await expect(args.onSelectionChange).toHaveBeenLastCalledWith(["p1", "p2"]);
  },
};

/** Select-all toggles every row on the current page. */
export const SelectAllPage: Story = {
  args: { selectable: true, pageSize: 5 },
  play: async ({ canvas }) => {
    await userEvent.click(
      canvas.getByRole("checkbox", { name: "Select all rows on this page" }),
    );
    await expect(canvas.getByText(/5 selected/)).toBeVisible();
  },
};

/** Client-side pagination. */
export const Pagination: Story = {
  args: { pageSize: 5 },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("Page 1 of 3")).toBeVisible();
    await userEvent.click(canvas.getByRole("button", { name: "Next" }));
    await expect(canvas.getByText("Page 2 of 3")).toBeVisible();
  },
};

/** The column menu hides/shows columns. */
export const ColumnVisibility: Story = {
  play: async ({ canvas }) => {
    await expect(
      canvas.getByRole("columnheader", { name: "Category" }),
    ).toBeVisible();
    await userEvent.click(canvas.getByRole("button", { name: "Columns" }));
    await userEvent.click(canvas.getByRole("checkbox", { name: "Category" }));
    await waitFor(() =>
      expect(
        canvas.queryByRole("columnheader", { name: "Category" }),
      ).not.toBeInTheDocument(),
    );
  },
};

export const Empty: Story = {
  args: { data: [] },
  play: async ({ canvas }) => {
    await expect(canvas.getByText("No data")).toBeVisible();
  },
};
