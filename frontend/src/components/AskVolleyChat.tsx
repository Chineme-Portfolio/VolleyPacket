"use client";

export interface ChatMsg {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
}

export const msgId = () => Date.now().toString() + Math.random().toString(36).slice(2);

interface AskVolleyChatProps {
  messages: ChatMsg[];
  input: string;
  onInput: (v: string) => void;
  onSend: () => void;
  onClear: () => void;
  generating: boolean;
  placeholder?: string;
  notice?: string;
  className?: string;
}

/**
 * "Ask Volley" chat panel — the shared AI conversation UI for templates, email, and SMS.
 * Presentational + controlled: the parent owns the messages/input state, persistence, and
 * what each turn does (apply to template / email / sms). The first message is treated as a
 * non-clearable welcome (Clear shows only when there's more than one message).
 */
export default function AskVolleyChat({
  messages,
  input,
  onInput,
  onSend,
  onClear,
  generating,
  placeholder,
  notice,
  className,
}: AskVolleyChatProps) {
  return (
    <div className={`flex flex-col border border-gray-100 rounded-xl overflow-hidden ${className || "h-[420px]"}`}>
      <div className="flex items-center justify-between px-4 py-1.5 bg-amber-50 border-b border-amber-100">
        <p className="text-[11px] text-amber-600">{notice || "Edits apply immediately and are saved with the job."}</p>
        {messages.length > 1 && (
          <button onClick={onClear} className="text-[11px] text-amber-500 hover:text-amber-700 transition-colors">
            Clear
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50/50">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "system" ? (
              <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                <div className="w-3 h-3 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
                {msg.text}
              </div>
            ) : (
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-green-800 text-white rounded-br-md"
                    : "bg-white border border-gray-200 text-gray-800 rounded-bl-md"
                }`}
              >
                {msg.text}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="px-4 py-3 border-t border-gray-100 bg-white">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => onInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && onSend()}
            placeholder={placeholder || "Ask Volley to draft or change this…"}
            className="flex-1 bg-gray-100 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 transition-shadow"
            disabled={generating}
          />
          <button
            onClick={onSend}
            disabled={generating || !input.trim()}
            className="flex-shrink-0 w-10 h-10 rounded-xl bg-green-800 flex items-center justify-center hover:bg-green-900 transition-colors disabled:opacity-50"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22L11 13L2 9L22 2Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
