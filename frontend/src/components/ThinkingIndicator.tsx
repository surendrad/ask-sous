/** Three-dot bounce loading state per design-guidelines.md §10, shown
 * while waiting for the first streamed chunk of an agent's answer. */
export function ThinkingIndicator() {
  return (
    <div
      role="status"
      aria-label="Ask Sous is thinking"
      className="flex items-center gap-1 rounded-full bg-elevated px-3 py-2"
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-text-muted motion-reduce:animate-none"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: "1.1s" }}
        />
      ))}
    </div>
  );
}
