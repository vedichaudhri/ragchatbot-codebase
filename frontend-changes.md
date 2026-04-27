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

---

# Frontend Code Quality Changes

## Overview

Added code quality tooling for the frontend (HTML, CSS, JavaScript) to enforce consistent formatting and catch common errors automatically.

## New Files

### `package.json`
Root-level npm manifest with dev dependencies and npm scripts:
- `npm run format` — auto-format all frontend files with Prettier
- `npm run format:check` — check formatting without modifying files (CI-safe)
- `npm run lint` — lint `frontend/script.js` with ESLint
- `npm run quality` — run both format check and lint in sequence

### `.prettierrc`
Prettier configuration applied to all frontend files:
- 2-space indentation, no tabs
- Single quotes in JavaScript
- Trailing commas in ES5 positions
- 80-character print width
- LF line endings

### `.eslintrc.json`
ESLint configuration for `frontend/script.js`:
- Browser + ES2021 globals enabled
- `marked` declared as a readonly global (loaded via CDN)
- Rules: `no-unused-vars` (warn), `no-console` (warn), `eqeqeq` (error), `no-var` (error)

### `scripts/check-frontend.sh`
Shell script that runs the full frontend quality pipeline in one command:
```bash
./scripts/check-frontend.sh
```
Runs `format:check` then `lint`, exiting non-zero on any failure.

## Modified Files

### `frontend/index.html`, `frontend/style.css`, `frontend/script.js`
All three files were reformatted by Prettier:
- Indentation changed from 4 spaces to 2 spaces
- Consistent single quotes in JavaScript
- Trailing commas added in ES5 positions

### `frontend/script.js` (additional changes)
- Removed two debug `console.log` calls from `loadCourseStats()` that were left over from development
- Added `// eslint-disable-next-line no-console` before the legitimate `console.error` in the catch block

## Usage

```bash
# Install dev dependencies (first time only)
npm install

# Auto-format all frontend files
npm run format

# Check formatting without writing (for CI)
npm run format:check

# Lint JavaScript
npm run lint

# Run all checks together
npm run quality

# Or use the convenience script
./scripts/check-frontend.sh
```
