# TODO — Kost Cerdas

## Django project foundation and real CSV source
- [x] Build the project as an individual Django web application, with the interface and documentation in Indonesian.
- [x] Use the actual `kos_madiun.csv` dataset from `https://github.com/SkyWee07/Sistem-Cerdas`; do not replace it with simulated data or another dataset.
- [x] Implement CSV import, field mapping, validation, and storage of kos records in the application database.

## Kos data browsing and database
- [x] Persist kos data in the application database and provide pages to browse the stored records and view individual kos details.
- [x] Read database configuration from environment variables, support Django migrations, and retain SQLite as a local-development fallback when the managed database URL is absent.

## Matplotlib dashboard
- [x] Provide a kos-data analytics dashboard with summary statistics and visualizations generated using Matplotlib.
- [x] Make the charts and summary values derive from the imported database data, not hard-coded or simulated values.

## Fuzzy suitability recommendations
- [x] Implement a standalone fuzzy system that scores kos suitability from user-provided criteria; fuzzy rules must not depend on having a separate training dataset.
- [x] Display ranked kos recommendations with a suitability score and a human-readable interpretation of each fuzzy result.

## AI explanation of charts and analysis
- [x] Integrate the Gemini API to generate Indonesian explanations of the dashboard charts and analysis.
- [x] Keep the API key in protected environment configuration; never commit it or expose it in browser code, templates, logs, or documentation.
- [x] Handle a missing key, provider/network errors, and invalid responses gracefully without breaking the rest of the application.

## Deployment readiness and documentation
- [x] Include production configuration, dependencies, container startup, and a health endpoint so the Django website can be deployed.
- [x] Document setup, dataset source and license status, API-key configuration, database migrations/import, application use, basic checks, and deployment in Indonesian.
- [x] Ensure the application can run locally and that deployment can use the configured persistent database instead of container-local files.
- [ ] Publish the Django website and provide its public URL after successful deployment.
