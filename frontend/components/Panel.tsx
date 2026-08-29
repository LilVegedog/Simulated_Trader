interface PanelProps {
  label: string;
  right?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  testId?: string;
  children: React.ReactNode;
}

/** Framed terminal section: an accent tick, a wide-tracked label, then the content. */
export function Panel({
  label,
  right,
  className = "",
  bodyClassName = "",
  testId,
  children,
}: PanelProps) {
  return (
    <section
      data-testid={testId}
      className={`flex min-h-0 min-w-0 flex-col border border-line bg-panel ${className}`}
    >
      <header className="flex h-8 shrink-0 items-center gap-2 border-b border-line-soft px-3">
        <span className="h-2.5 w-[2px] bg-accent" />
        <h2 className="eyebrow">{label}</h2>
        <div className="ml-auto flex items-center gap-2">{right}</div>
      </header>
      <div className={`min-h-0 min-w-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
