# Render deployment

The root `render.yaml` defines one Python web service in Frankfurt with a
1 GB persistent disk. This is a paid service: review Render's current price
before creating it. No GitHub Pages configuration is needed.

1. Connect Render to the GitHub repository `hsainezaid0/Job-Board-`.
2. Create a Blueprint from the repository's `main` branch.
3. Set `ADMIN_EMAIL` and a unique `ADMIN_PASSWORD` of at least 16 characters
   in Render's secret environment settings. Never commit the password.
4. Review the service and disk charges, then deploy.
5. Open the HTTPS URL Render provides, register a candidate, and log in as
   the administrator to create categories, companies, contacts, and jobs.

Production starts with an empty job board and one administrator; local demo
accounts and sample records are not installed. The login screen's example
credentials are for local demonstration only and will not work in production.
Existing local data is not uploaded. The admin environment settings only
bootstrap an empty database; changing them later does not reset an account.

The SQLite database and its WAL files live under `/var/data`, preserving
accounts and applications across restarts and deployments. Keep one service
instance. Deleting the disk deletes its data. Use SQLite's backup API to make
consistent backups and keep an off-service copy; persistence alone is not a
backup strategy.

Verify `/api/stats`, login, registration, job creation, and application submission
after deployment, then restart the service and confirm records remain.
Render terminates HTTPS and `COOKIE_SECURE=1` secures session cookies.
The app retains its existing standard-library HTTP server; this configuration
does not constitute a production security or load audit.
