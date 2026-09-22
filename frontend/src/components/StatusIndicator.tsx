type StatusIndicatorProps = {
  label: string;
  status: "checking" | "ready" | "offline";
};

const statusLabels = {
  checking: "CHECKING",
  ready: "READY",
  offline: "OFFLINE",
};

export function StatusIndicator({ label, status }: StatusIndicatorProps) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <span className={`status-pill status-pill--${status}`}>
        <span className="status-dot" aria-hidden="true" />
        {statusLabels[status]}
      </span>
    </div>
  );
}
