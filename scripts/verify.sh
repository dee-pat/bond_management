#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-pre-push}"
TEST_SITE_NAME="${TEST_SITE:-bond-management-test.localhost}"
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"

SEMGREP_VERSION="1.172.0"
# Vendored at the revision pinned in skills.lock.
FRAPPE_SEMGREP_RULES_DIR="${APP_ROOT}/semgrep/frappe"
APP_SEMGREP_RULES_FILE="${APP_ROOT}/semgrep/bond_management.yml"
APP_SEMGREP_TESTS_FILE="${APP_ROOT}/semgrep/tests/bond_management.py"

usage() {
    echo "Usage: scripts/verify.sh [lint|server|frontend|ui|playwright|pre-push|pre-push-ui|lifecycle|share-race]" >&2
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

run_semgrep() {
    local binary
    binary="$(semgrep_binary)"

    # semgrep/ holds rules and their test fixtures, which contain deliberate
    # findings, not app code.
    cd "${APP_ROOT}"
    echo "Running blocking Frappe Semgrep rules (ERROR severity)."
    "${binary}" scan \
        --error \
        --metrics=off \
        --disable-version-check \
        --config "${FRAPPE_SEMGREP_RULES_DIR}" \
        --severity ERROR \
        --exclude "semgrep"

    echo "Running advisory Frappe Semgrep rules."
    local advisory_status=0
    if "${binary}" scan \
        --metrics=off \
        --disable-version-check \
        --config "${FRAPPE_SEMGREP_RULES_DIR}" \
        --exclude "semgrep"; then
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
        --exclude "semgrep" \
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
    "${APP_ROOT}/scripts/sync-skills.sh" check
    run_semgrep

    local binary
    binary="$(semgrep_binary)"
    python3 "${APP_ROOT}/scripts/test_verify_semgrep.py" --semgrep "${binary}"
    python3 "${APP_ROOT}/scripts/test_claude_guard.py"
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

TEMPORARY_SITE=""
# Without DB_ROOT_PASSWORD, bench falls back to the bench's root_password.
DB_ROOT_ARGS=()
if [[ -n "${DB_ROOT_PASSWORD:-}" ]]; then
    DB_ROOT_ARGS=(--db-root-password "${DB_ROOT_PASSWORD}")
fi

drop_temporary_site() {
    if [[ -n "${TEMPORARY_SITE}" ]]; then
        cd "${BENCH_ROOT}"
        bench drop-site "${TEMPORARY_SITE}" --no-backup ${DB_ROOT_ARGS[@]+"${DB_ROOT_ARGS[@]}"}
        TEMPORARY_SITE=""
    fi
}

# Create a uniquely named <prefix><32-hex-id>.localhost site with the app
# installed and the given boolean flags set. The site is dropped on exit,
# whether the run passed or failed, after bench has printed its output.
create_temporary_site() {
    local prefix="$1"
    shift
    local site
    site="${prefix}$(python3 -c 'import uuid; print(uuid.uuid4().hex)').localhost"

    cd "${BENCH_ROOT}"
    TEMPORARY_SITE="${site}"
    trap drop_temporary_site EXIT
    bench new-site "${site}" --admin-password "$(python3 -c 'import secrets; print(secrets.token_hex(24))')" \
        ${DB_ROOT_ARGS[@]+"${DB_ROOT_ARGS[@]}"}
    local flag
    for flag in allow_tests "$@"; do
        bench --site "${site}" set-config "${flag}" true
    done
    bench --site "${site}" install-app bond_management
}

run_migration_lifecycle() {
    create_temporary_site "bond-management-lifecycle-" bond_migration_lifecycle_test
    local site="${TEMPORARY_SITE}"
    local phase="bond_management.bond_management.tests.migration_lifecycle"

    bench --site "${site}" execute "${phase}.fresh"
    bench --site "${site}" execute "${phase}.prepare"
    bench --site "${site}" migrate
    bench --site "${site}" execute "${phase}.verify"
    bench --site "${site}" execute "${phase}.requeue"
    bench --site "${site}" migrate
    bench --site "${site}" execute "${phase}.verify"
    bench --site "${site}" migrate
    bench --site "${site}" execute "${phase}.verify"
}

run_share_race() {
    local name
    for name in BOND_SHARE_LOCK_SOCKET BOND_SHARE_LOCK_USER; do
        if [[ -z "${!name:-}" ]]; then
            echo "${name} is required for the share-race check; see investor_share_concurrency.py." >&2
            exit 1
        fi
    done

    create_temporary_site "bond-management-race-"
    local site="${TEMPORARY_SITE}"
    local helper="bond_management.bond_management.tests.investor_share_concurrency"

    BOND_SHARE_RACE_BENCH="${BENCH_ROOT}"
    BOND_SHARE_RACE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
    export BOND_SHARE_RACE_BENCH BOND_SHARE_RACE_TOKEN
    bench --site "${site}" execute "${helper}.seed"
    bench --site "${site}" execute "${helper}.run"
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
    lifecycle)
        run_migration_lifecycle
        ;;
    share-race)
        run_share_race
        ;;
    *)
        usage
        exit 2
        ;;
esac
