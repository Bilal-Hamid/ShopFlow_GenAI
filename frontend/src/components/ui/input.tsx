import { forwardRef, useId, useState } from "react";

import { cn } from "@/lib/utils";

interface FieldFrameProps {
  fieldId: string;
  label?: string;
  helperText?: string;
  error?: string;
  /** Show "current / max" counter. Requires `maxLength` for the max. */
  showCount?: boolean;
  count: number;
  maxLength?: number;
  required?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}

/** Shared label + helper/error text + character-count chrome for form fields. */
function FieldFrame({
  fieldId,
  label,
  helperText,
  error,
  showCount,
  count,
  maxLength,
  required,
  disabled,
  children,
}: FieldFrameProps) {
  const helperId = `${fieldId}-helper`;
  const errorId = `${fieldId}-error`;

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={fieldId}
          className={cn(
            "text-sm font-medium",
            disabled
              ? "cursor-not-allowed text-muted-foreground"
              : "text-foreground",
          )}
        >
          {label}
          {required && (
            <span className="ml-0.5 text-destructive" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      {children}
      <div className="flex items-start justify-between gap-2">
        <p
          id={error ? errorId : helperId}
          className={cn(
            "text-xs",
            error ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {error ?? helperText}
        </p>
        {showCount && (
          <span
            className="shrink-0 text-xs tabular-nums text-muted-foreground"
            aria-hidden="true"
          >
            {count}
            {maxLength != null && `/${maxLength}`}
          </span>
        )}
      </div>
    </div>
  );
}

/** Derive the character count for both controlled and uncontrolled usage. */
function useCharCount(
  value: unknown,
  defaultValue: unknown,
): [number, (next: string) => void] {
  const [uncontrolledCount, setUncontrolledCount] = useState(
    String(defaultValue ?? "").length,
  );
  const isControlled = value != null;
  const count = isControlled ? String(value).length : uncontrolledCount;
  return [
    count,
    (next: string) => {
      if (!isControlled) setUncontrolledCount(next.length);
    },
  ];
}

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  /** Error message; also sets aria-invalid and error styling. */
  error?: string;
  /** Render a live character counter. */
  showCount?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      id,
      label,
      helperText,
      error,
      showCount,
      className,
      maxLength,
      required,
      disabled,
      value,
      defaultValue,
      onChange,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const fieldId = id ?? generatedId;
    const [count, updateCount] = useCharCount(value, defaultValue);
    const describedBy = error
      ? `${fieldId}-error`
      : helperText
        ? `${fieldId}-helper`
        : undefined;

    return (
      <FieldFrame
        fieldId={fieldId}
        label={label}
        helperText={helperText}
        error={error}
        showCount={showCount}
        count={count}
        maxLength={maxLength}
        required={required}
        disabled={disabled}
      >
        <input
          ref={ref}
          id={fieldId}
          value={value}
          defaultValue={defaultValue}
          maxLength={maxLength}
          required={required}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => {
            updateCount(e.target.value);
            onChange?.(e);
          }}
          className={cn(
            "flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-50",
            error
              ? "border-destructive focus-visible:ring-destructive"
              : "border-input focus-visible:ring-ring",
            className,
          )}
          {...props}
        />
      </FieldFrame>
    );
  },
);

Input.displayName = "Input";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helperText?: string;
  error?: string;
  showCount?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      id,
      label,
      helperText,
      error,
      showCount,
      className,
      maxLength,
      required,
      disabled,
      value,
      defaultValue,
      onChange,
      rows = 4,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const fieldId = id ?? generatedId;
    const [count, updateCount] = useCharCount(value, defaultValue);
    const describedBy = error
      ? `${fieldId}-error`
      : helperText
        ? `${fieldId}-helper`
        : undefined;

    return (
      <FieldFrame
        fieldId={fieldId}
        label={label}
        helperText={helperText}
        error={error}
        showCount={showCount}
        count={count}
        maxLength={maxLength}
        required={required}
        disabled={disabled}
      >
        <textarea
          ref={ref}
          id={fieldId}
          rows={rows}
          value={value}
          defaultValue={defaultValue}
          maxLength={maxLength}
          required={required}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => {
            updateCount(e.target.value);
            onChange?.(e);
          }}
          className={cn(
            "flex w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            "disabled:cursor-not-allowed disabled:opacity-50",
            error
              ? "border-destructive focus-visible:ring-destructive"
              : "border-input focus-visible:ring-ring",
            className,
          )}
          {...props}
        />
      </FieldFrame>
    );
  },
);

Textarea.displayName = "Textarea";
