Common commands:

# Start dev server
bench start

# Create app
bench new-app app_name

# Create site
bench new-site dev.local

# Install app
bench --site dev.local install-app app_name

# Migrate
bench --site dev.local migrate

# Build assets
bench build

# Clear cache
bench --site dev.local clear-cache

# Restart
bench restart

# Stop only this bench's processes after a broken state; inspect the PIDs first.
pgrep -af "${PWD}/apps/frappe|${PWD}/Procfile"
bench restart

# Start mariadb if not running
brew services start mariadb

# Backup
bench --site dev.local backup --with-files

# Shared verification (lint, migrate test_site, full server suite)
apps/bond_management/scripts/verify.sh pre-push

# Shared verification including the complete headless UI suite
apps/bond_management/scripts/verify.sh pre-push-ui

# Individual verification stages (`ui` expects an already prepared test site)
apps/bond_management/scripts/verify.sh lint
apps/bond_management/scripts/verify.sh server
apps/bond_management/scripts/verify.sh ui

# Cypress runtime diagnostics or repair (uses the bench-local cache)
apps/bond_management/scripts/cypress-runtime.sh diagnose
apps/bond_management/scripts/cypress-runtime.sh prepare
