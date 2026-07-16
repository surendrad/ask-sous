/**
 * Sets the `data-theme` attribute on <html> based on OS preference,
 * defaulting to dark (dark-first, per design-guidelines.md §13).
 *
 * No toggle UI yet — out of scope for Phase 0. A later phase that adds a
 * toggle control is also responsible for persisting the override to
 * localStorage.
 */
export function bootstrapTheme(): void {
  const prefersDark =
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : true;

  document.documentElement.dataset.theme = prefersDark ? "dark" : "light";
}
