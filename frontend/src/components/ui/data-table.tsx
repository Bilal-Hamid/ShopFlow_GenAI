"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface DataTableColumn<T> {
  /** Stable key; also used as the CSV header when `header` is a string. */
  key: string;
  header: string;
  /** Cell value accessor. */
  accessor: (row: T) => React.ReactNode;
  /** Raw value for sorting + CSV export (defaults to the accessor result). */
  sortValue?: (row: T) => string | number;
  sortable?: boolean;
  /** Hidden by default (still toggleable via the column menu). */
  defaultHidden?: boolean;
  className?: string;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  /** Unique row id — required for selection + React keys. */
  getRowId: (row: T) => string;
  caption?: string;
  selectable?: boolean;
  onSelectionChange?: (ids: string[]) => void;
  /** Rows per page. @default 10 */
  pageSize?: number;
  /** Show the column visibility toggle menu. @default true */
  columnToggle?: boolean;
  /** Show the "Export CSV" button. @default true */
  exportable?: boolean;
  /** Filename for the CSV export. @default "export.csv" */
  exportFileName?: string;
  className?: string;
}

type SortState = { key: string; dir: "asc" | "desc" } | null;

function toCsvValue(v: unknown): string {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * Generic, accessible data table with sortable columns, row selection,
 * client-side pagination, a column-visibility menu, and CSV export.
 */
export function DataTable<T>({
  columns,
  data,
  getRowId,
  caption,
  selectable = false,
  onSelectionChange,
  pageSize = 10,
  columnToggle = true,
  exportable = true,
  exportFileName = "export.csv",
  className,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(columns.filter((c) => c.defaultHidden).map((c) => c.key)),
  );
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the column menu on outside click (blur-to-close races the checkbox).
  useEffect(() => {
    if (!menuOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [menuOpen]);

  const visibleColumns = columns.filter((c) => !hidden.has(c.key));

  const sorted = useMemo(() => {
    if (!sort) return data;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return data;
    const value = (row: T) =>
      col.sortValue ? col.sortValue(row) : String(col.accessor(row) ?? "");
    return [...data].sort((a, b) => {
      const av = value(a);
      const bv = value(b);
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
  }, [data, sort, columns]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const clampedPage = Math.min(page, pageCount - 1);
  const pageRows = sorted.slice(
    clampedPage * pageSize,
    clampedPage * pageSize + pageSize,
  );

  const emitSelection = (next: Set<string>) => {
    setSelected(next);
    onSelectionChange?.([...next]);
  };

  const toggleRow = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    emitSelection(next);
  };

  const pageIds = pageRows.map(getRowId);
  const allPageSelected =
    pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const somePageSelected = pageIds.some((id) => selected.has(id));

  const toggleAllOnPage = () => {
    const next = new Set(selected);
    if (allPageSelected) pageIds.forEach((id) => next.delete(id));
    else pageIds.forEach((id) => next.add(id));
    emitSelection(next);
  };

  const toggleSort = (key: string) => {
    setSort((prev) =>
      prev?.key === key
        ? prev.dir === "asc"
          ? { key, dir: "desc" }
          : null
        : { key, dir: "asc" },
    );
  };

  const exportCsv = () => {
    const header = visibleColumns.map((c) => toCsvValue(c.header)).join(",");
    const rows = sorted.map((row) =>
      visibleColumns
        .map((c) =>
          toCsvValue(c.sortValue ? c.sortValue(row) : c.accessor(row)),
        )
        .join(","),
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {(columnToggle || exportable) && (
        <div className="flex items-center justify-end gap-2">
          {columnToggle && (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                aria-haspopup="true"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((o) => !o)}
                className="rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Columns
              </button>
              {menuOpen && (
                <div
                  role="group"
                  aria-label="Toggle columns"
                  className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
                >
                  {columns.map((c) => (
                    <label
                      key={c.key}
                      className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                    >
                      <input
                        type="checkbox"
                        className="accent-primary"
                        checked={!hidden.has(c.key)}
                        onChange={() => {
                          const next = new Set(hidden);
                          if (next.has(c.key)) next.delete(c.key);
                          else next.add(c.key);
                          setHidden(next);
                        }}
                      />
                      {c.header}
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
          {exportable && (
            <button
              type="button"
              onClick={exportCsv}
              className="rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Export CSV
            </button>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full border-collapse text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {selectable && (
                <th scope="col" className="w-10 px-3 py-2">
                  <input
                    type="checkbox"
                    className="accent-primary"
                    aria-label="Select all rows on this page"
                    checked={allPageSelected}
                    ref={(el) => {
                      if (el)
                        el.indeterminate = !allPageSelected && somePageSelected;
                    }}
                    onChange={toggleAllOnPage}
                  />
                </th>
              )}
              {visibleColumns.map((c) => {
                const active = sort?.key === c.key;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={
                      active
                        ? sort!.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : c.sortable
                          ? "none"
                          : undefined
                    }
                    className={cn(
                      "px-3 py-2 text-left font-medium text-muted-foreground",
                      c.className,
                    )}
                  >
                    {c.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key)}
                        className="inline-flex items-center gap-1 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {c.header}
                        <span aria-hidden="true" className="text-xs">
                          {active ? (sort!.dir === "asc" ? "▲" : "▼") : "↕"}
                        </span>
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={visibleColumns.length + (selectable ? 1 : 0)}
                  className="px-3 py-8 text-center text-muted-foreground"
                >
                  No data
                </td>
              </tr>
            )}
            {pageRows.map((row) => {
              const id = getRowId(row);
              const isSelected = selected.has(id);
              return (
                <tr
                  key={id}
                  data-selected={isSelected || undefined}
                  className={cn(
                    "border-b border-border last:border-0",
                    isSelected ? "bg-accent/50" : "hover:bg-muted/50",
                  )}
                >
                  {selectable && (
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        className="accent-primary"
                        aria-label={`Select row ${id}`}
                        checked={isSelected}
                        onChange={() => toggleRow(id)}
                      />
                    </td>
                  )}
                  {visibleColumns.map((c) => (
                    <td key={c.key} className={cn("px-3 py-2", c.className)}>
                      {c.accessor(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-4 text-sm text-muted-foreground">
        <span>
          {selectable && `${selected.size} selected · `}
          {sorted.length} row{sorted.length === 1 ? "" : "s"}
        </span>
        <div className="flex items-center gap-2">
          <span>
            Page {clampedPage + 1} of {pageCount}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={clampedPage === 0}
            className="rounded-md border border-input bg-background px-2 py-1 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={clampedPage >= pageCount - 1}
            className="rounded-md border border-input bg-background px-2 py-1 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
