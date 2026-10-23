#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-pre-push}"
TEST_SITE_NAME="${TEST_SITE:-bond-management-test.localhost}"
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"

SEMGREP_VERSION="1.172.0"
# Vendored at the revision pinned in skills.lock.
FRAPPE_SEMGREP_RULES_DIR="${APP_ROOT}/semgrep/frappe"
KIT_SEMGREP_RULES_DIR="${APP_ROOT}/semgrep/kit"

usage() {
    echo "Usage: scripts/verify.sh [lint|server|frontend|ui|playwright|pre-push|pre-push-ui|lifecycle|share-race] [playwright args]" >&2
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
    # findings, not app code. Every kit rule is ERROR severity, so the
    # severity filter keeps all of them blocking.
    cd "${APP_ROOT}"
    echo "Running blocking Semgrep rules (Frappe ERROR and frappe-agent-kit)."
    "${binary}" scan \
        --error \
        --metrics=off \
        --disable-version-check \
        --config "${FRAPPE_SEMGREP_RULES_DIR}" \
        --config "${KIT_SEMGREP_RULES_DIR}" \
        --severity ERROR \
        --exclude "semgrep"

    echo "Running advisory Frappe Semgrep rules (WARNING)."
    local advisory_status=0
    "${binary}" scan \
        --metrics=off \
        --disable-version-check \
        --config "${FRAPPE_SEMGREP_RULES_DIR}" \
        --severity WARNING \
        --exclude "semgrep" || advisory_status=$?

    if [[ "${advisory_status}" -gt 1 ]]; then
        echo "The advisory Semgrep scan failed with status ${advisory_status}." >&2
        exit "${advisory_status}"
    fi
}

run_lint() {
    cd "${APP_ROOT}"
    run_pre_commit
    "${APP_ROOT}/scripts/sync-skills.sh" check
    run_semgrep

    local binary
    binary="$(semgrep_binary)"
    python3 "${APP_ROOT}/scripts/test_verify_semgrep.py" --semgrep "${binary}"
    python3 "${APP_ROOT}/scripts/test_agent_policy.py"
    python3 "${APP_ROOT}/scripts/test_verify_helpers.py"
    python3 "${APP_ROOT}/scripts/test_deny_rules.py"
    python3 "${APP_ROOT}/scripts/test_doc_links.py"
    python3 "${APP_ROOT}/scripts/test_workflow_concurrency.py" \
        "${APP_ROOT}/.github/workflows/ci.yml" \
        "${APP_ROOT}/.github/workflows/linter.yml" \
        "${APP_ROOT}/.github/workflows/opt-in.yml"
}

run_server_tests() {
    prepare_test_site
    bench --site "${TEST_SITE_NAME}" run-tests --app bond_management
}

run_frontend_checks() {
    cd "${APP_ROOT}"
    yarn lint
    yarn typecheck
    yarn test:unit

    cd "${BENCH_ROOT}"
    bench build --app bond_management
}

prepare_playwright_site() {
    prepare_test_site
    bench --site "${TEST_SITE_NAME}" set-config bond_investor_spa_enabled 1
    bench --site "${TEST_SITE_NAME}" execute \
        bond_management.bond_management.tests.investor_ui_seed.seed_investor_ui_browser_test_data
}

BROWSER_CREDENTIAL_NAMES=(FRAPPE_USER FRAPPE_PASSWORD FRAPPE_ADMIN_USER FRAPPE_ADMIN_PASSWORD)
BROWSER_CREDENTIALS_HINT='export them or create $HOME/.config/bond_management/test-browser.env'

# Load and check the browser credentials with xtrace paused, so no value is
# traced. No caller has to source the credentials file.
prepare_browser_credentials() {
    local xtrace=""
    if [[ "$-" == *x* ]]; then
        xtrace=1
        set +x
    fi
    load_browser_credentials
    if [[ -z "${FRAPPE_USER:-}" ]] || [[ -z "${FRAPPE_PASSWORD:-}" ]]; then
        echo "FRAPPE_USER and FRAPPE_PASSWORD are required for investor browser tests; ${BROWSER_CREDENTIALS_HINT}." >&2
        exit 1
    fi
    if [[ -z "${FRAPPE_ADMIN_USER:-}" ]] || [[ -z "${FRAPPE_ADMIN_PASSWORD:-}" ]]; then
        echo "FRAPPE_ADMIN_USER and FRAPPE_ADMIN_PASSWORD are required for Desk browser tests; ${BROWSER_CREDENTIALS_HINT}." >&2
        exit 1
    fi
    if [[ -n "${xtrace}" ]]; then
        set -x
    fi
}

# Source the local credentials file when any browser variable is unset.
# Variables the caller already set win. The file's output and errors are
# discarded, so a malformed line cannot echo a value.
load_browser_credentials() {
    local file="${HOME:-}/.config/bond_management/test-browser.env"
    local name missing=""
    for name in "${BROWSER_CREDENTIAL_NAMES[@]}"; do
        if [[ -z "${!name:-}" ]]; then
            missing=1
        fi
    done
    if [[ -z "${missing}" ]] || [[ -z "${HOME:-}" ]] || [[ ! -f "${file}" ]]; then
        return 0
    fi

    for name in "${BROWSER_CREDENTIAL_NAMES[@]}"; do
        printf -v "CALLER_${name}" '%s' "${!name:-}"
    done
    # The file was written for an interactive shell, so errexit and nounset are
    # paused; bash 3.2 would otherwise exit silently inside it. The file may
    # enable xtrace itself, so xtrace stays off while values are copied.
    local status=0
    set -a +eu
    # shellcheck source=/dev/null
    source "${file}" >/dev/null 2>&1
    status=$?
    set +ax -eu
    if [[ "${status}" -ne 0 ]]; then
        echo "Could not load browser test credentials from ${file}." >&2
        exit 1
    fi
    local caller
    for name in "${BROWSER_CREDENTIAL_NAMES[@]}"; do
        caller="CALLER_${name}"
        if [[ -n "${!caller:-}" ]]; then
            printf -v "${name}" '%s' "${!caller}"
            export "${name}"
        fi
        unset "${caller}"
    done
}

run_playwright_tests() {
    prepare_browser_credentials

    prepare_playwright_site

    cd "${APP_ROOT}"
    if [[ ! -x "${APP_ROOT}/node_modules/.bin/playwright" ]]; then
        echo "Playwright is unavailable; install the app's root Node dependencies first." >&2
        exit 1
    fi

    local base_url="${BASE_URL:-${PLAYWRIGHT_BASE_URL:-http://localhost:8000}}"
    BASE_URL="${base_url}" yarn test:e2e "$@"
}

TEMPORARY_SITE=""
# Without DB_ROOT_PASSWORD, bench falls back to the bench's root_password.
DB_ROOT_ARGS=()
if [[ -n "${DB_ROOT_PASSWORD:-}" ]]; then
    DB_ROOT_ARGS=(--db-root-password "${DB_ROOT_PASSWORD}")
fi

# Run before every bench call on a temporary site, so a corrupted name can never
# reach a persistent or foreign site. The core never echoes the name.
require_temporary_site() {
    if ! python3 -I "${APP_ROOT}/bond_management/agent_policy.py" "$1"; then
        exit 1
    fi
}

drop_temporary_site() {
    if [[ -n "${TEMPORARY_SITE}" ]]; then
        require_temporary_site "${TEMPORARY_SITE}"
        cd "${BENCH_ROOT}"
        # Archive into a run-scoped directory and remove it once the drop succeeds,
        # so repeated runs do not accumulate site trees under archived/sites.
        local archive
        archive="$(mktemp -d "${TMPDIR:-/tmp}/bond-management-archive.XXXXXX")"
        bench drop-site "${TEMPORARY_SITE}" --no-backup --archived-sites-path "${archive}" \
            ${DB_ROOT_ARGS[@]+"${DB_ROOT_ARGS[@]}"}
        rm -rf "${archive}"
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
    require_temporary_site "${site}"

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
    ui | playwright)
        # Extra arguments go to Playwright, for example one spec and --project.
        run_playwright_tests "${@:2}"
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
