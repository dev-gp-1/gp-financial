# Playwright E2E Tests for GAA Financial Dashboard

This directory contains fresh, comprehensive Playwright end-to-end (E2E) tests for the GAA Financial Intelligence Platform dashboard. The tests cover the core features and user flows of the React/Vite/TypeScript application, including authentication, client portfolio monitoring, financial analytics, and human-in-the-loop (HITL) approval workflows.

## Prerequisites

- Node.js installed in your environment.
- Dashboard dependencies installed: `cd dashboard && npm install`
- Playwright browsers installed: `npx playwright install`

## Test Scenarios

The following scenarios are covered in the `e2e/` folder:

1. **Authentication Flow (`auth.spec.ts`)**: Verifies that the login page renders correctly, handles basic validation, and requires authentication for protected dashboard routes.
2. **Dashboard Layout (`dashboard_layout.spec.ts`)**: Verifies the main layout structure (header, footer), tab-based navigation (Portfolio, Analytics, Approvals), and features like theme toggling.
3. **Client Portfolio (`portfolio.spec.ts`)**: Verifies the interactive client health heatmap, client detail panels with AR/AP aging charts, and AI-powered agent recommendations.
4. **Analytics & Insights (`analytics.spec.ts`)**: Verifies the rendering of financial metrics and charts, date range filtering, and AI-generated insights powered by Gemini.
5. **HITL Approvals (`approvals.spec.ts`)**: Verifies the human-in-the-loop workflow for Mercury Bank payments, including the pending payments table and approve/reject actions.
6. **API Error Handling (`error_handling.spec.ts`)**: Verifies that the application gracefully handles backend unavailability and provides a retry mechanism.
7. **Legacy Tests (`dashboard.spec.ts`, `login.spec.ts`, `connectors.spec.ts`)**: These are existing tests that have been maintained for backward compatibility.

## Running the Tests

To run all E2E tests, use the following command from the `dashboard/` directory:

```bash
npm run test:e2e
```

To run a specific test file:

```bash
npx playwright test e2e/auth.spec.ts
```

To run tests with a visible UI (useful for debugging):

```bash
npx playwright test --ui
```

## Configuration

The tests are configured in `dashboard/playwright.config.ts`. By default, they target the local development server at `http://localhost:5173`. The configuration also includes settings for:

- **Parallel execution**: Enabled to speed up testing.
- **Retries**: Configured for CI environments to handle flakiness.
- **Reporting**: Generates an HTML report after each run.
- **Screenshots/Tracing**: Captures screenshots on failure and traces on first-retry to aid debugging.
- **Web Server**: Automatically starts the Vite dev server (`npm run dev`) if it's not already running.

## Mocking & Authentication

Currently, several dashboard-specific tests use `.skip()` because they require a mocked Firebase authentication session. In a production environment, you would use a test hook, a Firebase Emulator, or a service worker to intercept auth calls and provide a valid test user session.

See `dashboard/e2e/auth_utils.ts` for ongoing work on Firebase auth mocking utilities.
