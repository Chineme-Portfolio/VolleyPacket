export function statusBadge(status: string): string {
  const styles: Record<string, string> = {
    created: "bg-blue-100 text-blue-700",
    running: "bg-yellow-100 text-yellow-700",
    paused: "bg-amber-100 text-amber-700",
    complete: "bg-green-100 text-green-700",
    completed: "bg-green-100 text-green-700",
    cancelled: "bg-red-100 text-red-700",
    failed: "bg-red-100 text-red-700",
    interrupted: "bg-orange-100 text-orange-700",
    on_hold: "bg-purple-100 text-purple-700",
    archived: "bg-gray-200 text-gray-600",
  };
  return styles[status] || "bg-gray-100 text-gray-600";
}

const LABELS: Record<string, string> = {
  on_hold: "On hold",
};

/** Human-readable label for a status value (handles multi-word values like on_hold). */
export function statusLabel(status: string): string {
  if (LABELS[status]) return LABELS[status];
  return status ? status.charAt(0).toUpperCase() + status.slice(1) : status;
}

/** Statuses a user can manually set (an "Automatic" revert is offered separately). */
export const MANUAL_STATUSES: { value: string; label: string }[] = [
  { value: "created", label: "Created" },
  { value: "running", label: "Running" },
  { value: "complete", label: "Complete" },
  { value: "on_hold", label: "On hold" },
  { value: "cancelled", label: "Cancelled" },
  { value: "failed", label: "Failed" },
  { value: "archived", label: "Archived" },
];
