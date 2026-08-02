#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-pre-push}"
TEST_SITE_NAME="${TEST_SITE:-test_site}"
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"
export CYPRESS_CACHE_FOLDER="${BENCH_ROOT}/.cache/Cypress"

# These overrides affect the subsequent Frappe runner as well as the runtime
# preflight. Clear them in this parent process, not only inside the helper's
# child shell, so Electron is launched as an Electron app.
unset ELECTRON_RUN_AS_NODE CYPRESS_RUN_BINARY
if [[ -n "${CYPRESS_INSTALL_BINARY:-}" ]]; then
    unset CYPRESS_INSTALL_BINARY
fi

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
    "${APP_ROOT}/scripts/cypress-runtime.sh" prepare

    local chrome_binary="${CHROME_BIN:-}"
    if [[ -z "${chrome_binary}" ]]; then
        chrome_binary="$(command -v chrome || true)"
    fi
    if [[ -z "${chrome_binary}" ]]; then
        echo "Chrome was not found; set CHROME_BIN to the browser executable." >&2
        exit 1
    fi

    # Frappe assembles the Cypress command through a shell string. Pass the
    # browser by name and let CHROME_BIN carry the executable path so paths
    # containing spaces (such as the macOS application bundle) are preserved.
    export CHROME_BIN="${chrome_binary}"

    local -a cypress_args=(--headless --browser chrome)
    if [[ -n "${CYPRESS_SPEC:-}" ]]; then
        cypress_args+=(--spec "${CYPRESS_SPEC}")
    fi

    bench --site "${TEST_SITE_NAME}" run-ui-tests bond_management "${cypress_args[@]}"
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
