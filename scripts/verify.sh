#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-pre-push}"
TEST_SITE_NAME="${TEST_SITE:-test_site}"
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"

usage() {
    echo "Usage: scripts/verify.sh [lint|server|ui|pre-push|pre-push-ui]" >&2
}

prepare_test_site() {
    cd "${BENCH_ROOT}"
    bench --site "${TEST_SITE_NAME}" set-config allow_tests true
    bench --site "${TEST_SITE_NAME}" migrate
}

run_lint() {
    cd "${APP_ROOT}"

    if command -v pre-commit >/dev/null 2>&1; then
        pre-commit run --all-files
        return
    fi

    if [[ -x "${BENCH_ROOT}/env/bin/pre-commit" ]]; then
        "${BENCH_ROOT}/env/bin/pre-commit" run --all-files
        return
    fi

    echo "pre-commit is unavailable; run 'bench setup requirements --dev' from ${BENCH_ROOT}." >&2
    exit 1
}

run_server_tests() {
    prepare_test_site
    bench --site "${TEST_SITE_NAME}" run-tests --app bond_management
}

run_ui_tests() {
    local chrome_binary="${CHROME_BIN:-}"
    if [[ -z "${chrome_binary}" ]]; then
        chrome_binary="$(command -v chrome || true)"
    fi
    if [[ -z "${chrome_binary}" ]]; then
        echo "Chrome was not found; set CHROME_BIN to the browser executable." >&2
        exit 1
    fi

    bench --site "${TEST_SITE_NAME}" run-ui-tests bond_management \
        --headless \
        --browser "${chrome_binary}"
}

case "${MODE}" in
    lint)
        run_lint
        ;;
    server)
        run_server_tests
        ;;
    ui)
        run_ui_tests
        ;;
    pre-push)
        run_lint
        run_server_tests
        ;;
    pre-push-ui)
        run_lint
        run_server_tests
        run_ui_tests
        ;;
    *)
        usage
        exit 2
        ;;
esac
