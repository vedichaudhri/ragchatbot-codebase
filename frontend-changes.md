# Frontend Changes: Dark/Light Theme Toggle

## Files Modified

- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

---

## index.html

Added a `<button id="themeToggle" class="theme-toggle">` element immediately inside `<body>`, before `.container`. The button contains two inline SVG icons:

- `.icon-moon` — shown in dark mode (default); clicking switches to light mode
- `.icon-sun` — shown in light mode; clicking switches back to dark mode

Accessibility attributes: `aria-label="Toggle theme"` and `title="Toggle light/dark theme"`. The button is keyboard-navigable (standard `<button>` element).

---

## style.css

### New CSS variables

Added extra variables to `:root` for the toggle button surface colors (`--theme-toggle-bg`, `--theme-toggle-border`, `--theme-toggle-icon`, `--theme-toggle-hover-bg`) and a `--code-bg` variable so code blocks adapt to the active theme.

### `[data-theme="light"]` block

Added a complete light-theme override block applied when `<html data-theme="light">`:

| Variable | Light value |
|---|---|
| `--background` | `#f8fafc` |
| `--surface` | `#ffffff` |
| `--surface-hover` | `#e2e8f0` |
| `--text-primary` | `#0f172a` |
| `--text-secondary` | `#475569` |
| `--border-color` | `#e2e8f0` |
| `--shadow` | lighter RGBA shadow |
| `--code-bg` | `rgba(0,0,0,0.06)` |

Primary/accent colours (`--primary-color`, `--primary-hover`) stay the same in both themes.

### Global transition

Added a universal `transition` rule so every element animates background-color, border-color, color, and box-shadow over 0.25 s when the theme attribute changes.

### `.theme-toggle` styles

Fixed-position circle button (40 × 40 px, `border-radius: 50%`) at `top: 1rem; right: 1rem; z-index: 1000`. Hover and focus states use primary colour accents. `.icon-sun` / `.icon-moon` visibility is toggled via `display: none/block` conditioned on `[data-theme="light"]`.

---

## script.js

### `initTheme()`

Reads `localStorage.getItem('theme')` on load. Falls back to the OS `prefers-color-scheme` media query. Sets `data-theme` attribute on `<html>` accordingly.

### `toggleTheme()`

Reads the current `data-theme` attribute, flips it between `""` (dark) and `"light"`, and persists the choice to `localStorage`.

### `setupEventListeners()`

Added a click listener on `#themeToggle` that calls `toggleTheme()`.

### `DOMContentLoaded` handler

Added `initTheme()` call before `setupEventListeners()` so the correct theme is applied before any UI renders.
