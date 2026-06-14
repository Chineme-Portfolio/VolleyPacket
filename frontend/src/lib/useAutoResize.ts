import { useRef, useEffect } from "react";

/**
 * Auto-grow a <textarea> to fit its content, up to `maxPx`, then scroll.
 * Pass the controlled value so it re-measures on every change — including
 * collapsing back to one line when the value is cleared (e.g. after send).
 */
export function useAutoResize(value: string, maxPx = 140) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxPx)}px`;
  }, [value, maxPx]);
  return ref;
}
