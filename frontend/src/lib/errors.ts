/**
 * Centralized error handling — turns raw API/network errors into
 * user-friendly messages the frontend can display directly.
 */

/** Friendly message map by HTTP status code */
const STATUS_MESSAGES: Record<number, string> = {
  400: "Something was wrong with that request. Please check your input and try again.",
  401: "Your session has expired. Please sign in again.",
  403: "You don't have permission to do that.",
  404: "We couldn't find what you were looking for.",
  409: "There's a conflict — this action can't be completed right now.",
  413: "That file is too large. Please try a smaller one.",
  422: "Some of the information provided isn't valid. Please check and try again.",
  429: "Too many requests. Please wait a moment and try again.",
  500: "Something went wrong on our end. Please try again shortly.",
  502: "We're having trouble reaching a required service. Please try again.",
  503: "This feature is temporarily unavailable. Please try again later.",
};

/**
 * Parse a backend error response into a user-friendly message.
 *
 * The backend always returns `{ detail: "..." }` on errors.
 * Some detail strings are already user-friendly (e.g. "Email already registered").
 * Others are technical (e.g. "Stripe error: ..."). We surface the friendly ones
 * and fall back to generic status-based messages for the rest.
 */
const TECHNICAL_PATTERNS = [
  /traceback/i,
  /internal server/i,
  /stripe error:/i,
  /paystack error:/i,
  /^\[?errno/i,
  /connection refused/i,
  /database/i,
  /sqlalchemy/i,
  /pydantic/i,
  /unexpected token/i,
];

function isTechnicalMessage(detail: string): boolean {
  return TECHNICAL_PATTERNS.some((re) => re.test(detail));
}

/**
 * Given a fetch Response that is NOT ok, extract a friendly error message.
 */
export async function parseApiError(res: Response): Promise<string> {
  const status = res.status;

  // Try to read the JSON detail from the response
  let detail = "";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      // FastAPI validation errors come as an array
      detail = body.detail
        .map((d: { msg?: string; loc?: string[] }) => {
          const field = d.loc?.slice(-1)[0] || "field";
          return `${field}: ${d.msg || "invalid"}`;
        })
        .join(". ");
    }
  } catch {
    // Response wasn't JSON — use status text
    detail = res.statusText;
  }

  // If the detail is user-friendly, show it directly
  if (detail && !isTechnicalMessage(detail)) {
    return detail;
  }

  // Fall back to our status-based message
  return STATUS_MESSAGES[status] || `Request failed (${status}). Please try again.`;
}

/**
 * Wrap a network/fetch error into a friendly message.
 * Handles: network offline, DNS failure, CORS, timeouts.
 */
export function parseFetchError(err: unknown): string {
  if (err instanceof TypeError) {
    const msg = err.message.toLowerCase();
    if (msg.includes("failed to fetch") || msg.includes("networkerror")) {
      return "Can't reach the server. Please check your internet connection and try again.";
    }
    if (msg.includes("aborted") || msg.includes("timeout")) {
      return "The request took too long. Please try again.";
    }
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    return "The request was cancelled. Please try again.";
  }
  if (err instanceof Error) {
    // Already a friendly message from our own code
    return err.message;
  }
  return "Something went wrong. Please try again.";
}

/**
 * Convenience: a single function that handles both API errors and network errors.
 * Use in catch blocks: `setError(friendlyError(err))`
 */
export function friendlyError(err: unknown): string {
  return parseFetchError(err);
}
