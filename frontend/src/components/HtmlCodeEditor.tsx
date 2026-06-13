"use client";

import CodeMirror from "@uiw/react-codemirror";
import { html } from "@codemirror/lang-html";
import { EditorView } from "@codemirror/view";

interface HtmlCodeEditorProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * Syntax-highlighted HTML editor for the job template's HTML tab.
 * Isolated in its own module so it can be lazy-loaded via next/dynamic
 * (CodeMirror needs the DOM, and this keeps it off the initial bundle).
 */
export default function HtmlCodeEditor({ value, onChange }: HtmlCodeEditorProps) {
  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      height="100%"
      extensions={[html(), EditorView.lineWrapping]}
      className="h-full text-[13px]"
    />
  );
}
