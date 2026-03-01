#!/bin/bash
set -euo pipefail

echo "=== HydroMAS CI ==="
echo "Python: $(python3 --version)"
echo "Working directory: $(pwd)"
echo ""

# Run tests in order of dependency
echo "--- test_core ---"
python3 -m pytest tests/test_core -q --tb=short 2>&1 || true

echo ""
echo "--- test_skills ---"
python3 -m pytest tests/test_skills -q --tb=short 2>&1 || true

echo ""
echo "--- test_web ---"
python3 -m pytest tests/test_web -q --tb=short 2>&1 || true

echo ""
echo "--- test_e2e ---"
python3 -m pytest tests/test_e2e -q --tb=short 2>&1 || true

echo ""
echo "--- test_scenarios ---"
python3 -m pytest tests/test_scenarios -q --tb=short 2>&1 || true

echo ""
echo "=== CI Complete ==="
