import { forwardRef, useEffect, useId, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface SelectOption {
  label: string;
  value: string;
  disabled?: boolean;
}

export interface SelectOptionGroup {
  label: string;
  options: SelectOption[];
}

export type SelectOptions = SelectOption[] | SelectOptionGroup[];

function isGrouped(options: SelectOptions): options is SelectOptionGroup[] {
  return options.length > 0 && "options" in options[0]!;
}

/** Flatten groups to a single option list (used for lookups + keyboard nav). */
function flatten(options: SelectOptions): SelectOption[] {
  return isGrouped(options)
    ? options.flatMap((g) => g.options)
    : (options as SelectOption[]);
}

function filterOptions(options: SelectOptions, query: string): SelectOptions {
  if (!query) return options;
  const q = query.toLowerCase();
  const match = (o: SelectOption) => o.label.toLowerCase().includes(q);
  if (isGrouped(options)) {
    return options
      .map((g) => ({ ...g, options: g.options.filter(match) }))
      .filter((g) => g.options.length > 0);
  }
  return (options as SelectOption[]).filter(match);
}

export interface SelectProps {
  options: SelectOptions;
  /** Selected value(s). Controlled when provided. */
  value?: string | string[];
  defaultValue?: string | string[];
  onChange?: (value: string | string[]) => void;
  /** Allow selecting multiple values (renders removable chips). */
  multiple?: boolean;
  /** Show the in-dropdown search box. @default true */
  searchable?: boolean;
  placeholder?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
  /** Loading spinner in the dropdown (e.g. while async options resolve). */
  loading?: boolean;
  /**
   * Fetch options for the current query. Called on open and as the user types
   * (debounced). Replaces `options` while active.
   */
  loadOptions?: (query: string) => Promise<SelectOptions>;
  className?: string;
  name?: string;
}

/**
 * Accessible combobox with an optional search box, grouped options, multiple
 * selection, and async option loading. Follows the ARIA listbox pattern
 * (keyboard: ↑/↓ to move, Enter to select, Esc to close).
 */
export const Select = forwardRef<HTMLButtonElement, SelectProps>(
  (
    {
      options: optionsProp,
      value: valueProp,
      defaultValue,
      onChange,
      multiple = false,
      searchable = true,
      placeholder = "Select…",
      label,
      error,
      disabled = false,
      loading: loadingProp = false,
      loadOptions,
      className,
      name,
    },
    ref,
  ) => {
    const listboxId = useId();
    const rootRef = useRef<HTMLDivElement>(null);
    const searchRef = useRef<HTMLInputElement>(null);

    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [activeIndex, setActiveIndex] = useState(0);
    const [asyncOptions, setAsyncOptions] = useState<SelectOptions | null>(
      null,
    );
    const [asyncLoading, setAsyncLoading] = useState(false);

    const isControlled = valueProp !== undefined;
    const [internalValue, setInternalValue] = useState<string | string[]>(
      () => defaultValue ?? (multiple ? [] : ""),
    );
    const value = isControlled ? valueProp : internalValue;
    const selectedValues = multiple
      ? ((value as string[] | undefined) ?? [])
      : value
        ? [value as string]
        : [];

    const options = asyncOptions ?? optionsProp;
    const filtered = useMemo(
      // Async mode filters server-side, so don't re-filter locally.
      () => (loadOptions ? options : filterOptions(options, query)),
      [options, query, loadOptions],
    );
    const flat = useMemo(() => flatten(filtered), [filtered]);
    const loading = loadingProp || asyncLoading;

    const allOptions = useMemo(() => flatten(optionsProp), [optionsProp]);
    const labelFor = (v: string) =>
      flatten(options).find((o) => o.value === v)?.label ??
      allOptions.find((o) => o.value === v)?.label ??
      v;

    // Debounced async loading while open.
    useEffect(() => {
      if (!loadOptions || !open) return;
      let cancelled = false;
      setAsyncLoading(true);
      const t = setTimeout(() => {
        loadOptions(query)
          .then((res) => {
            if (!cancelled) setAsyncOptions(res);
          })
          .finally(() => {
            if (!cancelled) setAsyncLoading(false);
          });
      }, 250);
      return () => {
        cancelled = true;
        clearTimeout(t);
      };
    }, [loadOptions, open, query]);

    // Close on outside click.
    useEffect(() => {
      if (!open) return;
      const onDocClick = (e: MouseEvent) => {
        if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
      };
      document.addEventListener("mousedown", onDocClick);
      return () => document.removeEventListener("mousedown", onDocClick);
    }, [open]);

    // Focus the search box when opening.
    useEffect(() => {
      if (open && searchable) searchRef.current?.focus();
    }, [open, searchable]);

    const commit = (next: string | string[]) => {
      if (!isControlled) setInternalValue(next);
      onChange?.(next);
    };

    const toggleValue = (optValue: string) => {
      if (multiple) {
        const set = new Set(selectedValues);
        if (set.has(optValue)) set.delete(optValue);
        else set.add(optValue);
        commit([...set]);
      } else {
        commit(optValue);
        setOpen(false);
      }
    };

    const openMenu = () => {
      if (disabled) return;
      setOpen(true);
      setActiveIndex(0);
    };

    const onTriggerKeyDown = (e: React.KeyboardEvent) => {
      if (
        !open &&
        (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ")
      ) {
        e.preventDefault();
        openMenu();
      }
    };

    const onListKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, flat.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const opt = flat[activeIndex];
        if (opt && !opt.disabled) toggleValue(opt.value);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    };

    const describedBy = error ? `${listboxId}-error` : undefined;
    let renderIndex = -1;

    const renderOption = (opt: SelectOption) => {
      renderIndex += 1;
      const idx = renderIndex;
      const selected = selectedValues.includes(opt.value);
      return (
        <li
          key={opt.value}
          id={`${listboxId}-opt-${idx}`}
          role="option"
          aria-selected={selected}
          aria-disabled={opt.disabled || undefined}
          onMouseEnter={() => setActiveIndex(idx)}
          onMouseDown={(e) => {
            e.preventDefault();
            if (!opt.disabled) toggleValue(opt.value);
          }}
          className={cn(
            "flex cursor-pointer items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-sm",
            idx === activeIndex && "bg-accent text-accent-foreground",
            opt.disabled && "pointer-events-none opacity-50",
          )}
        >
          <span>{opt.label}</span>
          {selected && (
            <svg
              className="h-4 w-4 text-primary"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              aria-hidden="true"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </li>
      );
    };

    return (
      <div className={cn("flex flex-col gap-1.5", className)} ref={rootRef}>
        {label && (
          <span
            id={`${listboxId}-label`}
            className={cn(
              "text-sm font-medium",
              disabled ? "text-muted-foreground" : "text-foreground",
            )}
          >
            {label}
          </span>
        )}

        <div className="relative">
          <button
            ref={ref}
            type="button"
            role="combobox"
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-controls={open ? listboxId : undefined}
            aria-labelledby={label ? `${listboxId}-label` : undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            disabled={disabled}
            onClick={() => (open ? setOpen(false) : openMenu())}
            onKeyDown={onTriggerKeyDown}
            className={cn(
              "flex min-h-10 w-full items-center justify-between gap-2 rounded-md border bg-background px-3 py-1.5 text-left text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              "disabled:cursor-not-allowed disabled:opacity-50",
              error
                ? "border-destructive focus-visible:ring-destructive"
                : "border-input focus-visible:ring-ring",
            )}
          >
            <span className="flex flex-1 flex-wrap gap-1">
              {selectedValues.length === 0 && (
                <span className="text-muted-foreground">{placeholder}</span>
              )}
              {multiple
                ? selectedValues.map((v) => (
                    <span
                      key={v}
                      className="inline-flex items-center gap-1 rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground"
                    >
                      {labelFor(v)}
                      <span
                        role="button"
                        tabIndex={-1}
                        aria-label={`Remove ${labelFor(v)}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          toggleValue(v);
                        }}
                        className="rounded-full hover:text-destructive"
                      >
                        <svg
                          className="h-3 w-3"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          aria-hidden="true"
                        >
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </span>
                    </span>
                  ))
                : selectedValues[0] && (
                    <span>{labelFor(selectedValues[0])}</span>
                  )}
            </span>
            <svg
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-180",
              )}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {/* Native hidden input(s) so the value participates in forms. */}
          {name &&
            (multiple ? (
              selectedValues.map((v) => (
                <input key={v} type="hidden" name={name} value={v} />
              ))
            ) : (
              <input
                type="hidden"
                name={name}
                value={selectedValues[0] ?? ""}
              />
            ))}

          {open && (
            <div
              className="absolute z-50 mt-1 w-full rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
              onKeyDown={onListKeyDown}
            >
              {searchable && (
                <input
                  ref={searchRef}
                  type="text"
                  role="searchbox"
                  aria-label="Search options"
                  value={query}
                  placeholder="Search…"
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActiveIndex(0);
                  }}
                  className="mb-1 w-full rounded-sm border border-input bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              )}
              <ul
                id={listboxId}
                role="listbox"
                aria-multiselectable={multiple || undefined}
                aria-label={label ?? placeholder}
                className="max-h-60 overflow-auto"
              >
                {loading && (
                  <li className="px-2 py-4 text-center text-sm text-muted-foreground">
                    Loading…
                  </li>
                )}
                {!loading && flat.length === 0 && (
                  <li className="px-2 py-4 text-center text-sm text-muted-foreground">
                    No results
                  </li>
                )}
                {!loading &&
                  (isGrouped(filtered)
                    ? filtered.map((group) => (
                        <li key={group.label} role="presentation">
                          <div className="px-2 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {group.label}
                          </div>
                          <ul role="group" aria-label={group.label}>
                            {group.options.map(renderOption)}
                          </ul>
                        </li>
                      ))
                    : (filtered as SelectOption[]).map(renderOption))}
              </ul>
            </div>
          )}
        </div>

        {error && (
          <p id={describedBy} className="text-xs text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  },
);

Select.displayName = "Select";

/** Multi-select preset — `Select` with `multiple` forced on. */
export const MultiSelect = forwardRef<
  HTMLButtonElement,
  Omit<SelectProps, "multiple">
>((props, ref) => <Select ref={ref} multiple {...props} />);

MultiSelect.displayName = "MultiSelect";
