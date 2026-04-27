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
