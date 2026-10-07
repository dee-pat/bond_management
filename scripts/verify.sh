#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-pre-push}"
TEST_SITE_NAME="${TEST_SITE:-test_site}"
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"

SEMGREP_VERSION="1.172.0"
FRAPPE_SEMGREP_RULES_REPOSITORY="https://github.com/frappe/semgrep-rules.git"
FRAPPE_SEMGREP_RULES_SHA="de085539bc9b4d74eb0a2ac508d21f33495be733"
FRAPPE_SEMGREP_RULES_CACHE="${BENCH_ROOT}/.cache/frappe-semgrep-rules/${FRAPPE_SEMGREP_RULES_SHA}"
APP_SEMGREP_RULES_FILE="${APP_ROOT}/semgrep/bond_management.yml"
APP_SEMGREP_TESTS_FILE="${APP_ROOT}/semgrep/tests/bond_management.py"

usage() {
    echo "Usage: scripts/verify.sh [lint|server|frontend|ui|playwright|pre-push|pre-push-ui]" >&2
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
        --error \
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
        --error \
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
    python3 "${APP_ROOT}/scripts/test_verify_semgrep.py" \
        --semgrep "$(semgrep_binary)" \
        --frappe-rules "$(frappe_semgrep_rules_dir)"
}

run_server_tests() {
    prepare_test_site
    bench --site "${TEST_SITE_NAME}" run-tests --app bond_management
}

run_frontend_checks() {
    cd "${APP_ROOT}"
    yarn lint
    yarn typecheck

    cd "${BENCH_ROOT}"
    bench build --app bond_management
}

prepare_playwright_site() {
    prepare_test_site
    bench --site "${TEST_SITE_NAME}" set-config bond_investor_spa_enabled 1
    bench --site "${TEST_SITE_NAME}" execute \
        bond_management.bond_management.tests.investor_ui_seed.seed_investor_ui_browser_test_data
}

run_playwright_tests() {
    if [[ -z "${FRAPPE_USER:-}" ]] || [[ -z "${FRAPPE_PASSWORD:-}" ]]; then
        echo "FRAPPE_USER and FRAPPE_PASSWORD are required for investor browser tests." >&2
        exit 1
    fi
    if [[ -z "${FRAPPE_ADMIN_USER:-}" ]] || [[ -z "${FRAPPE_ADMIN_PASSWORD:-}" ]]; then
        echo "FRAPPE_ADMIN_USER and FRAPPE_ADMIN_PASSWORD are required for Desk browser tests." >&2
        exit 1
    fi

    prepare_playwright_site

    cd "${APP_ROOT}"
    if [[ ! -x "${APP_ROOT}/node_modules/.bin/playwright" ]]; then
        echo "Playwright is unavailable; install the app's root Node dependencies first." >&2
        exit 1
    fi

    local base_url="${BASE_URL:-${PLAYWRIGHT_BASE_URL:-http://localhost:8000}}"
    BASE_URL="${base_url}" yarn test:e2e
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return
fi

case "${MODE}" in
    lint)
        run_lint
        ;;
    server)
        run_server_tests
        ;;
    frontend)
        run_frontend_checks
        ;;
    ui)
        run_playwright_tests
        ;;
    playwright)
        run_playwright_tests
        ;;
    pre-push)
        run_lint
        run_server_tests
        ;;
    pre-push-ui)
        run_lint
        run_server_tests
        run_frontend_checks
        run_playwright_tests
        ;;
    *)
        usage
        exit 2
        ;;
esac
