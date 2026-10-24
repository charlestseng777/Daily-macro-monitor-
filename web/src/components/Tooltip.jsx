// Hover/focus tooltip. Content stays in text ink; colour lives on the mark.
export default function Tooltip({ content, children, className = '' }) {
  return (
    <span className={`group relative inline-flex ${className}`} tabIndex={0}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-max max-w-[260px] -translate-x-1/2 rounded-lg border border-line bg-raised px-3 py-2 text-xs leading-relaxed text-ink-2 hidden shadow-xl group-hover:block group-focus:block"
      >
        {content}
      </span>
    </span>
  );
}
