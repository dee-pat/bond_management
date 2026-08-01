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

# Kill bench and Redis after broken state before bench start
pkill -f bench & sudo pkill -f redis

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
