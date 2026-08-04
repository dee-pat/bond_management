#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-pre-push}"
TEST_SITE_NAME="${TEST_SITE:-test_site}"
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"
export CYPRESS_CACHE_FOLDER="${BENCH_ROOT}/.cache/Cypress"

SEMGREP_VERSION="1.172.0"
FRAPPE_SEMGREP_RULES_REPOSITORY="https://github.com/frappe/semgrep-rules.git"
FRAPPE_SEMGREP_RULES_SHA="de085539bc9b4d74eb0a2ac508d21f33495be733"
FRAPPE_SEMGREP_RULES_CACHE="${BENCH_ROOT}/.cache/frappe-semgrep-rules/${FRAPPE_SEMGREP_RULES_SHA}"
APP_SEMGREP_RULES_FILE="${APP_ROOT}/semgrep/bond_management.yml"
APP_SEMGREP_TESTS_FILE="${APP_ROOT}/semgrep/tests/bond_management.py"

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

run_pre_commit() {
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

semgrep_binary() {
    local binary="${SEMGREP_BIN:-}"

    if [[ -z "${binary}" ]] && command -v semgrep >/dev/null 2>&1; then
        binary="$(command -v semgrep)"
    fi

    if [[ -z "${binary}" ]] && [[ -x "${BENCH_ROOT}/env/bin/semgrep" ]]; then
        binary="${BENCH_ROOT}/env/bin/semgrep"
    fi

    if [[ -z "${binary}" ]] || [[ ! -x "${binary}" ]]; then
        echo "Semgrep is unavailable; run 'bench setup requirements --dev' from ${BENCH_ROOT}." >&2
        exit 1
    fi

    local installed_version
    installed_version="$("${binary}" --version)"
    if [[ "${installed_version}" != "${SEMGREP_VERSION}" ]]; then
        echo "Expected Semgrep ${SEMGREP_VERSION}, found ${installed_version}." >&2
        exit 1
    fi

    printf '%s\n' "${binary}"
}

frappe_semgrep_rules_dir() {
    local rules_dir="${FRAPPE_SEMGREP_RULES_DIR:-${FRAPPE_SEMGREP_RULES_CACHE}}"

    if [[ -n "${FRAPPE_SEMGREP_RULES_DIR:-}" ]]; then
        if [[ ! -d "${rules_dir}/.git" ]]; then
            echo "FRAPPE_SEMGREP_RULES_DIR must be a git checkout." >&2
            exit 1
        fi
    elif [[ ! -d "${rules_dir}/.git" ]]; then
        if [[ -e "${rules_dir}" ]]; then
            echo "Semgrep rules cache path exists but is not a git checkout: ${rules_dir}" >&2
            exit 1
        fi

        mkdir -p "$(dirname "${rules_dir}")"
        git init -q "${rules_dir}"
        git -C "${rules_dir}" remote add origin "${FRAPPE_SEMGREP_RULES_REPOSITORY}"
        git -C "${rules_dir}" fetch -q --depth 1 origin "${FRAPPE_SEMGREP_RULES_SHA}"
        git -C "${rules_dir}" checkout -q --detach "${FRAPPE_SEMGREP_RULES_SHA}"
    fi

    local checked_out_sha
    checked_out_sha="$(git -C "${rules_dir}" rev-parse HEAD)"
    if [[ "${checked_out_sha}" != "${FRAPPE_SEMGREP_RULES_SHA}" ]]; then
        echo "Expected Frappe Semgrep rules ${FRAPPE_SEMGREP_RULES_SHA}, found ${checked_out_sha}." >&2
        exit 1
    fi

    printf '%s\n' "${rules_dir}"
}

run_semgrep() {
    local binary
    binary="$(semgrep_binary)"

    local rules_dir
    rules_dir="$(frappe_semgrep_rules_dir)"

    cd "${APP_ROOT}"
    echo "Running blocking Frappe Semgrep rules (ERROR severity)."
    "${binary}" scan \
        --metrics=off \
        --disable-version-check \
        --config "${rules_dir}/rules" \
        --severity ERROR \
        --exclude "semgrep/tests"

    echo "Running advisory Frappe Semgrep rules."
    local advisory_status=0
    if "${binary}" scan \
        --metrics=off \
        --disable-version-check \
        --config "${rules_dir}/rules" \
        --exclude "semgrep/tests"; then
        advisory_status=0
    else
        advisory_status=$?
    fi

    if [[ "${advisory_status}" -gt 1 ]]; then
        echo "The advisory Semgrep scan failed with status ${advisory_status}." >&2
        exit "${advisory_status}"
    fi

    echo "Running blocking Bond Management Semgrep rules."
    "${binary}" scan \
        --metrics=off \
        --disable-version-check \
        --config "${APP_SEMGREP_RULES_FILE}" \
        --exclude "semgrep/tests" \
        "${APP_ROOT}"

    echo "Running Bond Management Semgrep rule tests."
    (
        cd "${APP_ROOT}/semgrep"
        "${binary}" --test --strict --test-ignore-todo \
            --config bond_management.yml \
            tests/bond_management.py
    )
}

run_lint() {
    cd "${APP_ROOT}"
    run_pre_commit
    run_semgrep
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
