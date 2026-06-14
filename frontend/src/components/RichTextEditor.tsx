"use client";

import { useRef, useEffect } from "react";

interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  className?: string;
}

/**
 * Lightweight WYSIWYG for an HTML *fragment* (e.g. an email body) — a contenteditable
 * div + a small formatting toolbar (document.execCommand). No iframe: the body is a
 * fragment, not a full document, so there's no <style>/@page to preserve.
 *
 * Controlled by `value`/`onChange` (HTML string). External value changes are pushed into
 * the DOM only when the editor isn't focused, so typing is never interrupted.
 */
export default function RichTextEditor({ value, onChange, className }: RichTextEditorProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el && el.innerHTML !== (value || "") && document.activeElement !== el) {
      el.innerHTML = value || "";
    }
  }, [value]);

  function emit() {
    if (ref.current) onChange(ref.current.innerHTML);
  }

  function exec(command: string, val?: string) {
    document.execCommand(command, false, val);
    emit();
  }

  const iconBtn = "w-8 h-8 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-gray-50";
  const textBtn = "h-8 px-2 rounded-lg border border-gray-200 text-xs text-gray-700 hover:bg-gray-50";

  return (
    <div className={`flex flex-col ${className || "h-[420px]"}`}>
      <div className="flex flex-wrap items-center gap-1 mb-2">
        {[
          { cmd: "bold", label: "B", cls: "font-bold" },
          { cmd: "italic", label: "I", cls: "italic" },
          { cmd: "underline", label: "U", cls: "underline" },
        ].map((b) => (
          <button key={b.cmd} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec(b.cmd)} className={`${iconBtn} ${b.cls}`}>
            {b.label}
          </button>
        ))}
        <span className="w-px h-5 bg-gray-200 mx-1" />
        {[
          { cmd: "insertUnorderedList", label: "• List" },
          { cmd: "insertOrderedList", label: "1. List" },
        ].map((b) => (
          <button key={b.cmd} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec(b.cmd)} className={textBtn}>
            {b.label}
          </button>
        ))}
        <span className="w-px h-5 bg-gray-200 mx-1" />
        {[
          { cmd: "justifyLeft", label: "↤" },
          { cmd: "justifyCenter", label: "↔" },
          { cmd: "justifyRight", label: "↦" },
        ].map((b) => (
          <button key={b.cmd} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec(b.cmd)} className={iconBtn}>
            {b.label}
          </button>
        ))}
        <span className="w-px h-5 bg-gray-200 mx-1" />
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            const url = window.prompt("Link URL:");
            if (url) exec("createLink", url);
          }}
          className={textBtn}
        >
          Link
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec("removeFormat")} className={textBtn}>
          Clear
        </button>
      </div>

      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        onInput={emit}
        className="flex-1 overflow-auto rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-800 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
      />
    </div>
  );
}
