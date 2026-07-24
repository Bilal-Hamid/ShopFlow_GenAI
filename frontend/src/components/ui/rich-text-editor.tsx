"use client";

import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";

export interface RichTextEditorProps {
  /** Initial HTML content (uncontrolled — Tiptap owns the document). */
  defaultValue?: string;
  /** Fires with the current HTML on every edit. */
  onChange?: (html: string) => void;
  label?: string;
  helperText?: string;
  error?: string;
  disabled?: boolean;
  className?: string;
}

interface ToolButtonProps {
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function ToolButton({
  label,
  active,
  disabled,
  onClick,
  children,
}: ToolButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:pointer-events-none disabled:opacity-50",
        active
          ? "bg-primary text-primary-foreground"
          : "text-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Minimal rich-text editor (Tiptap) for product descriptions. Toolbar covers
 * bold, italic, bullet + ordered lists, and links. Renders an accessible
 * textbox and emits HTML via `onChange`.
 */
export function RichTextEditor({
  defaultValue = "",
  onChange,
  label,
  helperText,
  error,
  disabled = false,
  className,
}: RichTextEditorProps) {
  const id = useId();
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");

  const editor = useEditor({
    immediatelyRender: false,
    editable: !disabled,
    extensions: [
      StarterKit.configure({
        link: { openOnClick: false, HTMLAttributes: { rel: "noopener" } },
      }),
    ],
    content: defaultValue,
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": label ?? "Rich text editor",
        class:
          "min-h-32 w-full rounded-b-md px-3 py-2 text-sm focus:outline-none prose-editor",
      },
    },
    onUpdate: ({ editor: e }) => onChange?.(e.getHTML()),
  });

  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      bold: e?.isActive("bold") ?? false,
      italic: e?.isActive("italic") ?? false,
      bulletList: e?.isActive("bulletList") ?? false,
      orderedList: e?.isActive("orderedList") ?? false,
      link: e?.isActive("link") ?? false,
    }),
  });

  const applyLink = () => {
    if (!editor) return;
    const url = linkUrl.trim();
    if (url) {
      editor
        .chain()
        .focus()
        .extendMarkRange("link")
        .setLink({ href: url })
        .run();
    } else {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
    }
    setLinkOpen(false);
    setLinkUrl("");
  };

  const describedBy = error
    ? `${id}-error`
    : helperText
      ? `${id}-helper`
      : undefined;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <span
          className={cn(
            "text-sm font-medium",
            disabled ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {label}
        </span>
      )}

      <div
        aria-describedby={describedBy}
        className={cn(
          "rounded-md border bg-background",
          error ? "border-destructive" : "border-input",
          // Signal disabled via a muted surface (not opacity) so the text
          // stays above the WCAG AA contrast threshold.
          disabled && "cursor-not-allowed bg-muted",
        )}
      >
        <div
          role="toolbar"
          aria-label="Formatting"
          aria-controls={id}
          className="flex items-center gap-1 border-b border-border p-1"
        >
          <ToolButton
            label="Bold"
            active={state?.bold}
            disabled={disabled}
            onClick={() => editor?.chain().focus().toggleBold().run()}
          >
            <span className="font-bold">B</span>
          </ToolButton>
          <ToolButton
            label="Italic"
            active={state?.italic}
            disabled={disabled}
            onClick={() => editor?.chain().focus().toggleItalic().run()}
          >
            <span className="italic">I</span>
          </ToolButton>
          <span className="mx-1 h-5 w-px bg-border" aria-hidden="true" />
          <ToolButton
            label="Bullet list"
            active={state?.bulletList}
            disabled={disabled}
            onClick={() => editor?.chain().focus().toggleBulletList().run()}
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
          </ToolButton>
          <ToolButton
            label="Numbered list"
            active={state?.orderedList}
            disabled={disabled}
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="10" y1="6" x2="21" y2="6" />
              <line x1="10" y1="12" x2="21" y2="12" />
              <line x1="10" y1="18" x2="21" y2="18" />
              <path d="M4 6h1v4" />
              <path d="M4 10h2" />
              <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" />
            </svg>
          </ToolButton>
          <span className="mx-1 h-5 w-px bg-border" aria-hidden="true" />
          <ToolButton
            label="Link"
            active={state?.link || linkOpen}
            disabled={disabled}
            onClick={() => {
              setLinkUrl(editor?.getAttributes("link").href ?? "");
              setLinkOpen((o) => !o);
            }}
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
          </ToolButton>
        </div>

        {linkOpen && (
          <div className="flex items-center gap-2 border-b border-border p-2">
            <input
              type="url"
              aria-label="Link URL"
              placeholder="https://example.com"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  applyLink();
                }
              }}
              className="flex-1 rounded-sm border border-input bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <button
              type="button"
              onClick={applyLink}
              className="rounded-sm bg-primary px-2 py-1 text-sm text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Apply
            </button>
          </div>
        )}

        <div id={id}>
          <EditorContent editor={editor} />
        </div>
      </div>

      {(error || helperText) && (
        <p
          id={describedBy}
          className={cn(
            "text-xs",
            error ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {error ?? helperText}
        </p>
      )}
    </div>
  );
}
