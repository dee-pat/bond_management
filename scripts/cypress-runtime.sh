#!/usr/bin/env bash

set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_ROOT="$(cd "${APP_ROOT}/../.." && pwd)"
FRAPPE_ROOT="${BENCH_ROOT}/apps/frappe"
FRAPPE_NODE_MODULES="${FRAPPE_ROOT}/node_modules"
CYPRESS_BIN="${FRAPPE_NODE_MODULES}/.bin/cypress"
# Keep this value in sync with the GitHub Actions cache key and Frappe v16's
# supported UI-test dependency set. Do not allow an environment override to
# pair the runner with a binary from a different cache.
CYPRESS_VERSION="13.17.0"
DEFAULT_CYPRESS_CACHE_FOLDER="${BENCH_ROOT}/.cache/Cypress"
CYPRESS_CACHE_FOLDER="${CYPRESS_CACHE_FOLDER:-${DEFAULT_CYPRESS_CACHE_FOLDER}}"
CYPRESS_VERIFY_TIMEOUT="${CYPRESS_VERIFY_TIMEOUT:-120000}"

if [[ "${CYPRESS_CACHE_FOLDER}" != "${DEFAULT_CYPRESS_CACHE_FOLDER}" ]]; then
	echo "Ignoring custom Cypress cache; using ${DEFAULT_CYPRESS_CACHE_FOLDER}."
	CYPRESS_CACHE_FOLDER="${DEFAULT_CYPRESS_CACHE_FOLDER}"
fi
export CYPRESS_CACHE_FOLDER CYPRESS_VERIFY_TIMEOUT

# Some IDEs (including the Codex runner) set this flag globally so Electron
# launches as a Node process. Cypress is an Electron application and must be
# allowed to start normally; otherwise its smoke-test flags are rejected.
if [[ -n "${ELECTRON_RUN_AS_NODE:-}" ]]; then
	echo "Ignoring ELECTRON_RUN_AS_NODE for Cypress (it must run as an Electron app)."
	unset ELECTRON_RUN_AS_NODE
fi

# Do not let a machine-wide binary or an install-disable flag bypass the
# deterministic bench-local runtime managed by this script.
if [[ -n "${CYPRESS_RUN_BINARY:-}" ]]; then
	echo "Ignoring CYPRESS_RUN_BINARY; the bench-local Cypress binary is required."
	unset CYPRESS_RUN_BINARY
fi
if [[ -n "${CYPRESS_INSTALL_BINARY:-}" ]]; then
	echo "Ignoring CYPRESS_INSTALL_BINARY; the pinned Cypress binary must be installed."
	unset CYPRESS_INSTALL_BINARY
fi

# Frappe v16 installs this dependency set from run-ui-tests when it is absent.
# Keep the versions explicit here so local and CI runs do not silently drift.
REQUIRED_PACKAGES=(
	"cypress:${CYPRESS_VERSION}"
	"@4tw/cypress-drag-drop:2.3.1"
	"cypress-real-events:1.15.0"
	"@testing-library/cypress:10.1.3"
	"@testing-library/dom:8.17.1"
	"@cypress/code-coverage:3.14.7"
	"cypress-split:1.25.0"
)

usage() {
	echo "Usage: scripts/cypress-runtime.sh [prepare|diagnose]" >&2
}

package_version() {
	local package_name="$1"
	local package_json="${FRAPPE_NODE_MODULES}/${package_name}/package.json"

	if [[ ! -f "${package_json}" ]]; then
		return 1
	fi

	node -e 'console.log(require(process.argv[1]).version)' "${package_json}"
}

print_diagnostics() {
	echo "Cypress cache: ${CYPRESS_CACHE_FOLDER}"
	if [[ -x "${CYPRESS_BIN}" ]]; then
		"${CYPRESS_BIN}" version || true
		"${CYPRESS_BIN}" cache list || true
	else
		echo "Cypress CLI: missing at ${CYPRESS_BIN}"
	fi
}

check_node() {
	if ! command -v node >/dev/null 2>&1; then
		echo "Node.js is required for Frappe v16 Cypress tests." >&2
		exit 1
	fi

	local node_major
	node_major="$(node -p 'process.versions.node.split(".")[0]')"
	if [[ "${node_major}" != "24" ]]; then
		echo "Frappe v16 UI tests require Node 24; found Node ${node_major}." >&2
		exit 1
	fi

	if ! command -v yarn >/dev/null 2>&1; then
		echo "Yarn is required to install Frappe's Cypress dependencies." >&2
		exit 1
	fi
}

dependencies_are_pinned() {
	local requirement package_name expected actual
	for requirement in "${REQUIRED_PACKAGES[@]}"; do
		package_name="${requirement%%:*}"
		expected="${requirement#*:}"
		if ! actual="$(package_version "${package_name}")" || [[ "${actual}" != "${expected}" ]]; then
			return 1
		fi
	done
}

verify_cypress() {
	local verify_log verify_status
	verify_log="$(mktemp)"

	set +e
	"${CYPRESS_BIN}" verify 2>&1 | tee "${verify_log}"
	verify_status="${PIPESTATUS[0]}"
	set -e

	if [[ "${verify_status}" -eq 0 ]]; then
		rm -f "${verify_log}"
		return 0
	fi

	# A process-level abort means the host cannot launch this Electron build
	# (for example, an unsupported macOS release or unavailable GUI session).
	# Re-downloading the same binary cannot repair that condition and can hide
	# the useful diagnostic behind a network error.
	if grep -Eq "SIGABRT|SIGSEGV|Abort trap" "${verify_log}"; then
		echo "Cypress could not start on this host; the binary was not re-downloaded." >&2
		rm -f "${verify_log}"
		return 2
	fi

	rm -f "${verify_log}"
	return "${verify_status}"
}

install_pinned_dependencies() {
	local package_json="${FRAPPE_ROOT}/package.json"
	local backup requirement package_name expected
	local -a yarn_packages=()

	if [[ ! -f "${package_json}" ]]; then
		echo "Frappe package.json was not found at ${package_json}." >&2
		exit 1
	fi

	# Frappe's own command temporarily adds these packages and restores its
	# manifest. Do the same, while making the versions deterministic. The
	# installed node_modules are intentionally retained for the test run.
	(
		set -euo pipefail
		backup="$(mktemp)"
		cp "${package_json}" "${backup}"
		restore_manifest() {
			cp "${backup}" "${package_json}"
			rm -f "${backup}"
		}
		trap restore_manifest EXIT

		cd "${FRAPPE_ROOT}"
		for requirement in "${REQUIRED_PACKAGES[@]}"; do
			package_name="${requirement%%:*}"
			expected="${requirement#*:}"
			yarn_packages+=("${package_name}@${expected}")
		done
		yarn add --no-lockfile --exact "${yarn_packages[@]}"
	)
}

prepare() {
	check_node
	mkdir -p "${CYPRESS_CACHE_FOLDER}"

	if ! dependencies_are_pinned; then
		echo "Installing the pinned Frappe v16 Cypress runtime..."
		install_pinned_dependencies
	fi

	if ! dependencies_are_pinned; then
		echo "The installed Cypress dependencies do not match the pinned versions." >&2
		print_diagnostics
		exit 1
	fi
	if [[ ! -x "${CYPRESS_BIN}" ]]; then
		echo "The pinned Cypress package is installed but its CLI is missing at ${CYPRESS_BIN}." >&2
		exit 1
	fi

	print_diagnostics
	if verify_cypress; then
		:
	else
		verify_status="$?"
		if [[ "${verify_status}" -eq 2 ]]; then
			exit 1
		fi
		echo "Cypress verification failed; reinstalling its binary in the bench-local cache..." >&2
		"${CYPRESS_BIN}" install --force
		verify_cypress
	fi
}

case "${1:-prepare}" in
	prepare)
		prepare
		;;
	diagnose)
		check_node
		print_diagnostics
		;;
	*)
		usage
		exit 2
		;;
esac
