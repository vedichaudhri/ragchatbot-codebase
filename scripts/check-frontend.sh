#!/bin/bash
set -e

echo "Running frontend quality checks..."
echo ""

echo "Checking formatting with Prettier..."
npm run format:check
echo "  Formatting OK"
echo ""

echo "Linting JavaScript with ESLint..."
npm run lint
echo "  Lint OK"
echo ""

echo "All frontend quality checks passed!"
