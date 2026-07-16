# Ask Sous — Design Guidelines

**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Design Philosophy

Three principles guide every design decision in Ask Sous:

- **Grounded, not decorative.** The product's entire pitch is "never a made-up number." The UI shows its work — tool-call citations, source chips — rather than hiding the machinery behind confident-sounding prose.
- **Calm data density.** The audience is a restaurant owner, not an analyst. Chat comes first; charts and tables support it, they don't overwhelm it.
- **Fast feels honest.** Since correctness is the whole pitch, the interface should feel snappy and responsive, so nothing reads as hiding a slow or uncertain process.

Decision record: `docs/showcase-colour-palette.html`, `docs/showcase-typography.html`, `docs/showcase-icons.html`, `docs/showcase-components.html`, `docs/showcase-layouts.html`, `docs/showcase-motion.html` capture the options considered and are kept as implementation reference.

---

## 2. Brand Colour

**Direction: Warm Ember** — a terracotta/amber brand tone that ties back to hospitality and warmth without tipping into a generic "restaurant red." Distinctive enough to be worth talking about in an interview setting, and it pairs naturally with Fraunces' organic, warm serif curves.

| Mode | Brand | On-brand (text/icon on brand fill) |
|---|---|---|
| Dark | `#ec6a3e` | `#1c0c04` |
| Light | `#c8471f` | `#ffffff` |

---

## 3. Colour System

All colours are semantic tokens — never reference a hex value directly in component code.

### 3.1 Dark mode (primary)

| Token | Value | Usage |
|---|---|---|
| `--base` | `#150f0b` | App background |
| `--surface` | `#1d1611` | Sidebar, panel backgrounds |
| `--elevated` | `#261d17` | Cards, inputs, dropdown/modal surfaces |
| `--overlay` | `#2f251d` | Hover states on `elevated`, toggle track off-state |
| `--border` | `#3a2d22` | Default borders, dividers |
| `--border-strong` | `#4a3a2c` | Input borders, emphasized dividers |
| `--text` | `#f8ede4` | Primary text |
| `--text-secondary` | `#cbb6a5` | Secondary text, body copy in cards |
| `--text-muted` | `#8f7a67` | Captions, placeholders, metadata |
| `--brand` | `#ec6a3e` | Primary actions, active nav, links |
| `--on-brand` | `#1c0c04` | Text/icons on brand-filled surfaces |
| `--brand-wash` | `rgba(236,106,62,0.16)` | Selected/active backgrounds, "AI generated" tag |
| `--brand-text` | `#f4936c` | Text on brand-wash backgrounds |
| `--success` / `--success-text` | `#65c179` / `#8fd6a0` | Positive trend, success states |
| `--success-wash` | `rgba(101,193,121,0.16)` | Success tag background |
| `--error` / `--error-text` | `#f0665f` / `#f5928c` | Negative trend, destructive actions, validation errors |
| `--error-wash` | `rgba(240,102,95,0.16)` | Error tag background |
| `--warning-text` | `#f0c05c` | Warning tag text (e.g. "Tuesday consistently slow") |
| `--warning-wash` | `rgba(240,180,60,0.16)` | Warning tag background |
| `--info-text` | `#7fb0fb` | Tool-call/citation chips, model-routing indicators |
| `--info-wash` | `rgba(110,168,254,0.16)` | Citation chip background |

### 3.2 Light mode

| Token | Value | Usage |
|---|---|---|
| `--base` | `#fffaf6` | App background |
| `--surface` | `#fbf2ea` | Sidebar, panel backgrounds |
| `--elevated` | `#ffffff` | Cards, inputs, dropdown/modal surfaces |
| `--overlay` | `#f6e9dd` | Hover states, toggle track off-state |
| `--border` | `#ecdbc9` | Default borders, dividers |
| `--border-strong` | `#ddc4a8` | Input borders, emphasized dividers |
| `--text` | `#241811` | Primary text |
| `--text-secondary` | `#5f4a3b` | Secondary text |
| `--text-muted` | `#8c7663` | Captions, placeholders |
| `--brand` | `#c8471f` | Primary actions, active nav, links |
| `--on-brand` | `#ffffff` | Text/icons on brand-filled surfaces |
| `--brand-wash` | `rgba(200,71,31,0.10)` | Selected/active backgrounds |
| `--brand-text` | `#b03e1a` | Text on brand-wash backgrounds |
| `--success` / `--success-text` | `#15803d` | Positive trend, success states |
| `--success-wash` | `rgba(21,128,61,0.10)` | Success tag background |
| `--error` / `--error-text` | `#c0392b` | Negative trend, destructive, validation |
| `--error-wash` | `rgba(192,57,43,0.10)` | Error tag background |
| `--warning-text` | `#93650c` | Warning tag text |
| `--warning-wash` | `rgba(180,120,10,0.12)` | Warning tag background |
| `--info-text` | `#1d4ed8` | Citation chips, model-routing indicators |
| `--info-wash` | `rgba(29,78,216,0.10)` | Citation chip background |

### 3.3 Contrast

All text/background pairs above meet WCAG 2.1 AA (4.5:1 for body text, 3:1 for large text/UI components). Do not introduce a new colour pairing without checking contrast — reuse existing tokens.

---

## 4. Typography

**Pairing: Fraunces (display/headings) + Inter (UI/body) + JetBrains Mono (numbers/citations).**

Fraunces is a warm, characterful serif with soft, organic curves, used *only* for display text and headings — it gives the product a hospitality feel without sacrificing legibility, since all dense UI text (chat messages, labels, nav, data) stays in Inter. JetBrains Mono is reserved for anything numeric or code-like: dollar amounts, percentages, tool-call names — reinforcing that these values are computed, not prose.

Load via Google Fonts:
```
family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700
family=Inter:wght@400;500;600;700
family=JetBrains+Mono:wght@400;500;600
```

### Type scale

| Token | Font | Size/Line-height | Weight | Usage |
|---|---|---|---|---|
| Display | Fraunces | 34px / 40px | 600 | Page-level headlines (rare — e.g. an empty-state headline) |
| Title | Fraunces | 23px / 30px | 600 | View titles ("Chat", "Campaigns", "Dashboard"), modal titles |
| Heading | Inter | 17px / 24px | 600 | Card/section headings |
| Body | Inter | 14px / 22px | 400 | Chat messages, paragraph copy |
| Label | Inter | 12px / 16px | 600, uppercase, 0.04em tracking | Field labels, stat card keys |
| Caption | Inter | 11px / 16px | 500 | Metadata, timestamps, tool-call captions |
| Mono | JetBrains Mono | matches surrounding scale | 500–600 | Currency, percentages, tool/function names |

Body text and UI chrome never use Fraunces — it is reserved for moments that benefit from personality (view titles, modal titles, empty-state headlines), not dense information.

---

## 5. Spacing & Layout

4px base unit.

| Token | Value |
|---|---|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-10` | 40px |
| `--space-12` | 48px |
| `--space-16` | 64px |

### App shell

- **Sidebar:** 224px fixed width. Contains brand mark, restaurant switcher, nav items (Chat / Campaigns / Dashboard), and a footer status line (live-trickle state, active model).
- **Layout approach: split view.** Chat and the Campaigns panel are visible side by side (`grid-template-columns: 224px 1.6fr 1fr`) — the owner watches a campaign draft populate live while still able to keep asking questions, without switching screens. This was chosen over separate full-screen views specifically for its demo value: it's the single clearest visual proof of "grounded generation," which is the project's whole point.
- **Dashboard** is a separate full-width view (not part of the split), reached via the sidebar nav.
- **Breakpoints:** desktop split view above ~1024px; below that, the campaigns panel and dashboard become separate destinations even in the split-view approach (there's no viable narrower split). Below ~768px (mobile), the sidebar collapses to a bottom tab bar (Chat / Campaigns / Dashboard) and every view is single-column, full-width.

---

## 6. Border Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 6px | Checkboxes, small tags, dropdown items |
| `--radius-md` | 10px | Buttons, inputs, stat cards, dropdown menus |
| `--radius-lg` | 14px | Cards, panels, app shell frame |
| `--radius-xl` | 20px | Modals |
| `--radius-full` | 999px | Pills/tags, avatars, toggles |

Soft but not playful — rounded enough to feel approachable (matching the hospitality warmth of the palette and Fraunces), restrained enough to stay credible as a data tool.

---

## 7. Shadows & Elevation

Dark mode relies primarily on background lightness + borders for elevation, since shadows barely read against a dark base; light mode uses soft shadows.

| Level | Dark | Light | Usage |
|---|---|---|---|
| e1 | `0 1px 2px rgba(0,0,0,0.3)` | `0 1px 2px rgba(36,24,17,0.05), 0 1px 3px rgba(36,24,17,0.04)` | Cards at rest |
| e2 | `0 8px 24px rgba(0,0,0,0.35)` | `0 4px 16px rgba(36,24,17,0.08)` | Card hover, dropdown menus, app shell frame |
| e3 | `0 20px 60px rgba(0,0,0,0.5)` | `0 20px 60px rgba(36,24,17,0.18)` | Modals |

---

## 8. Components

Full interactive reference: `docs/definition/design-system.html`. Key decisions:

- **Buttons:** four variants — primary (brand fill), secondary (bordered, `elevated` fill), ghost (text-only), danger (`error` fill). Three sizes (sm/md/lg). States: default, hover (brightness +8% or `overlay` background), active (brightness -6% or scale 0.96), disabled (42% opacity), loading (75% opacity + spinning icon).
- **Inputs:** text, textarea, select share one style — `elevated` background, `border-strong` border, `radius-md`. Focus: brand border + 3px brand-wash ring. Error: error border + error-wash ring + inline error message with icon. Disabled: 50% opacity.
- **Checkboxes:** 18px, `radius-sm`, brand fill + white checkmark when checked. **Toggles:** 38×22px pill, brand fill + knob slide when on.
- **Cards:** `elevated` background, `radius-lg`, e1 shadow at rest, e2 + 1px lift on hover (150ms snappy). Stat cards use the mono type scale for the value.
- **Tags/chips:** fully rounded (`radius-full`), semantic wash/text colour pairs (brand/success/warning/error/info/neutral). The **info** variant is reserved specifically for tool-call/citation chips and model-routing indicators — kept visually distinct from the brand-coloured "AI generated" tag so grounding data never looks the same as generated content.
- **Avatars:** circular, brand-wash background with brand-text initials fallback; stacked groups overlap by -8px with a 2px surface-coloured border.
- **Dropdown menus:** `elevated` surface, e2 shadow, items highlight with brand-wash on hover/focus; destructive items get error-wash on hover. Open/close animates 140ms snappy (opacity + translateY(-6px) + scale 0.98 → full).
- **Modals:** centered, `radius-xl`, e3 shadow, backdrop `rgba(10,6,4,0.6)` with 2px blur. Open animates 180ms snappy (opacity + scale 0.94→1 + translateY(8px)→0).
- **Empty states:** dashed `border-strong` container, brand-wash icon badge, Fraunces heading, muted body copy, primary CTA.
- **Navigation:** sidebar nav items use brand-wash + brand-text + 600 weight when active; tabs use a 2px brand underline.

---

## 9. Icons

**Lucide** — outlined, 2px stroke, consistent corner radius. It's the default icon set shadcn/ui expects, so there's zero extra integration work beyond the stack choice already made.

Sizes: 16px (inline/dense contexts), 20px (default UI), 24px (empty states, feature callouts). Load via `lucide` UMD script or the `lucide-react` package once building the actual app.

Core icon vocabulary for this product: `message-circle` (chat), `megaphone` (campaigns), `bar-chart-3` (dashboard), `send`, `wrench` (tool call), `trending-up`/`trending-down`, `alert-triangle`, `store` (restaurant), `refresh-cw` (regenerate), `sparkles` (AI generated), `chevron-down` (switcher/dropdowns).

---

## 10. Motion & Animation

**Timing: Snappy — 150ms, `cubic-bezier(0.2, 0.8, 0.3, 1)` (ease-out).** Chosen because correctness is the product's whole pitch; motion that lingers reads as masking latency or hiding uncertainty, which works against the "grounded" story. Bouncy/spring motion was ruled out for the same reason — it undercuts a trustworthy, data-tool tone.

| Interaction | Treatment |
|---|---|
| Button hover/press | Brightness shift on hover; `scale(0.96)` on active/press |
| Card hover | `translateY(-2px)` + shadow e1→e2 |
| Dropdown open | opacity 0→1, `translateY(-6px) scale(0.98)` → full, 140ms |
| Modal open | opacity 0→1, `scale(0.94) translateY(8px)` → full, 180ms, backdrop fades in parallel |
| Chat message streaming | Text reveals incrementally with a blinking brand-coloured cursor (2px wide, `blink` 0.9s step-end) |
| Thinking/loading state | Three-dot bounce, staggered 0.15s, 1.1s ease-in-out loop |
| Citation chip reveal | Fades and slides up 4px, 220ms snappy, ~150ms delay after the answer text lands — so grounding evidence visibly follows the claim |
| Campaign regenerate | Card border flashes brand colour and pulses outward (`box-shadow` 0→8px spread), 500ms, on new copy landing |

`prefers-reduced-motion: reduce` collapses all of the above to instant state changes — content still appears/updates, just without slide/scale/pulse motion.

---

## 11. View-Specific Patterns

- **Chat (left/center panel):** message list (user messages right-aligned brand-filled bubbles, agent messages left-aligned `elevated` bubbles with border), inline stat cards for numeric answers, citation chips under any agent message that states a number, input bar pinned to the bottom.
- **Campaigns (right panel in split view / full view on mobile):** stacked campaign cards, each with channel tag (SMS/Email), copy preview, Regenerate + Copy actions. New-campaign affordance as a dashed placeholder card.
- **Dashboard:** KPI stat-card row + two chart cards (revenue trend as a 7-day bar chart, top items as a ranked list with inline proportional bars) — nice-to-have per the master plan, not core to the agent story, so it stays simple (CSS-drawn bars, no charting library needed for the demo's visual weight).
- **Restaurant switcher:** lives at the top of the sidebar, always visible, opens the same dropdown-menu pattern used elsewhere.

---

## 12. Accessibility

Non-negotiable, applied throughout:

- WCAG 2.1 AA contrast on all text/background and UI-component/background pairs (verified for every token pair in §3).
- Full keyboard navigation: dropdowns and modals are focus-trapped and close on `Escape`; all interactive elements are reachable via Tab in a logical order.
- Semantic HTML and ARIA roles where native semantics fall short (e.g. `role="dialog"` + `aria-modal` on modals, `aria-expanded` on dropdown triggers).
- Minimum 44×44px touch targets on all interactive elements, even where the visual element is smaller (e.g. icon-only buttons get padding to reach the minimum).
- `prefers-reduced-motion: reduce` and `prefers-color-scheme` are both respected (see §10 and §13).

---

## 13. Dark/Light Mode Implementation

Dark-first: dark mode is the primary, default experience; light mode is fully designed and equally supported, not an afterthought. Implementation approach:

- All colour tokens are defined as CSS custom properties scoped under `[data-theme="dark"]` / `[data-theme="light"]` on the root element (see §3 for full token tables).
- Default to `prefers-color-scheme` on first load; persist an explicit user override (if the app adds a toggle) to `localStorage`.
- No component should ever reference a raw hex value — always the semantic token, so theme switching is automatic.

---

## 14. Summary: Quick Reference

- **Brand colour:** `#ec6a3e` (dark) / `#c8471f` (light) — Warm Ember
- **Fonts:** Fraunces (display/headings) + Inter (UI/body) + JetBrains Mono (numbers)
- **Type scale:** Display 34/40·600, Title 23/30·600, Heading 17/24·600, Body 14/22·400, Label 12/16·600 caps, Caption 11/16·500
- **Spacing scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64
- **Radii:** sm 6 / md 10 / lg 14 / xl 20 / full 999
- **Shadows:** e1 (rest) / e2 (hover, dropdowns) / e3 (modals) — dark relies on borders+lightness, light uses soft shadows
- **Icons:** Lucide, 2px stroke, 16/20/24px
- **Motion:** 150ms snappy ease-out (`cubic-bezier(0.2, 0.8, 0.3, 1)`) as default; respects `prefers-reduced-motion`
- **Layout:** 224px sidebar + split view (chat + campaigns panel), dashboard as separate view, mobile collapses to bottom tab bar below ~768px
- **Breakpoints:** mobile <768px (single column, bottom tabs) · tablet 768–1024px (narrower split or stacked) · desktop >1024px (full split view)
- **Mode:** dark-first, light fully supported, both AA-contrast checked
