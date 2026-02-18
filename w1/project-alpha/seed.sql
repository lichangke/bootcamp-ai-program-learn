\set ON_ERROR_STOP on

BEGIN;

-- Reset all core tables so the seed is repeatable.
TRUNCATE TABLE ticket_tags, tickets, tags RESTART IDENTITY CASCADE;

-- 50 tags: platform, project, and functional dimensions.
INSERT INTO tags (name) VALUES
  ('ios'),
  ('android'),
  ('web'),
  ('backend'),
  ('frontend'),
  ('api'),
  ('mobile'),
  ('desktop'),
  ('windows'),
  ('macos'),
  ('linux'),
  ('viking'),
  ('odin'),
  ('hermes'),
  ('atlas'),
  ('artemis'),
  ('autocomplete'),
  ('search'),
  ('pagination'),
  ('filtering'),
  ('notifications'),
  ('authentication'),
  ('authorization'),
  ('reporting'),
  ('analytics'),
  ('export'),
  ('import'),
  ('caching'),
  ('performance'),
  ('accessibility'),
  ('localization'),
  ('dark-mode'),
  ('onboarding'),
  ('billing'),
  ('invoicing'),
  ('payments'),
  ('retry'),
  ('logging'),
  ('monitoring'),
  ('security'),
  ('refactor'),
  ('bug'),
  ('ux'),
  ('ci-cd'),
  ('testing'),
  ('postgres'),
  ('docs'),
  ('release'),
  ('infra'),
  ('observability');

-- 50 meaningful tickets across product, platform, and engineering topics.
-- NOTE: status/check constraints require completed_at to be non-null when status = 'done'.
INSERT INTO tickets (title, description, status, completed_at) VALUES
  ('Implement iOS push notification settings', 'Allow users to opt in per notification category on iOS.', 'open', NULL),
  ('Add Android offline sync retry queue', 'Queue failed writes on Android and retry with backoff.', 'open', NULL),
  ('Redesign web ticket list empty state', 'Improve clarity and call to action for empty ticket lists.', 'open', NULL),
  ('Build autocomplete for tag selector', 'Provide keyboard friendly tag suggestions in editor dialog.', 'open', NULL),
  ('Optimize ticket search query with trigram index', 'Reduce response time for fuzzy title queries.', 'open', NULL),
  ('Add pagination controls to ticket list', 'Add first and last page actions with page size control.', 'open', NULL),
  ('Create project Viking milestone dashboard', 'Show milestone health, blockers, and ETA in one view.', 'open', NULL),
  ('Integrate Odin release checklist workflow', 'Convert manual Odin launch checklist into trackable tasks.', 'open', NULL),
  ('Implement Hermes webhook signature validation', 'Reject unsigned or tampered webhook payloads.', 'open', NULL),
  ('Add Atlas tenant onboarding wizard', 'Guide new Atlas tenants through first project setup.', 'open', NULL),
  ('Improve Artemis role assignment UX', 'Reduce confusion while assigning roles and permissions.', 'open', NULL),
  ('Enable CSV export for ticket reports', 'Export filtered ticket lists to CSV for operations team.', 'open', NULL),
  ('Add bulk import for legacy tickets', 'Migrate legacy backlog using validated CSV templates.', 'open', NULL),
  ('Introduce caching for tag list endpoint', 'Cache frequently requested tag list responses.', 'open', NULL),
  ('Add API rate limiting middleware', 'Protect API endpoints from accidental flood traffic.', 'open', NULL),
  ('Improve accessibility for keyboard navigation', 'Ensure all major interactions are reachable by keyboard.', 'open', NULL),
  ('Add localization for zh-CN copy', 'Translate critical user flows for Chinese locale.', 'open', NULL),
  ('Build dark mode theme toggle', 'Add persistent light and dark theme preference.', 'open', NULL),
  ('Implement SSO login for enterprise users', 'Support enterprise SSO providers for login.', 'open', NULL),
  ('Add billing plan upgrade screen', 'Allow account owners to change subscription plan.', 'open', NULL),
  ('Generate monthly invoicing summary job', 'Create invoice summaries and billing audit lines.', 'open', NULL),
  ('Add payment failure retry policy', 'Retry failed payment attempts with bounded strategy.', 'open', NULL),
  ('Add structured logging for API errors', 'Standardize server error logs for easier triage.', 'open', NULL),
  ('Build Grafana dashboards for ticket latency', 'Monitor request latency and saturation trends.', 'open', NULL),
  ('Harden auth token refresh flow', 'Close edge cases around token expiry and rotation.', 'open', NULL),
  ('Refactor ticket service validation rules', 'Consolidate validation paths and error mapping.', 'open', NULL),
  ('Fix race condition in tag delete cascade', 'Prevent stale tag references during concurrent deletes.', 'done', NOW() - INTERVAL '17 days'),
  ('Add E2E smoke test for ticket lifecycle', 'Cover create, edit, complete, reopen, and delete path.', 'done', NOW() - INTERVAL '16 days'),
  ('Add CI pipeline for backend lint and tests', 'Run lint and unit tests for every pull request.', 'done', NOW() - INTERVAL '15 days'),
  ('Add frontend unit tests for dialog forms', 'Increase confidence for ticket and tag dialogs.', 'done', NOW() - INTERVAL '14 days'),
  ('Improve mobile responsive layout on dashboard', 'Fix layout breakpoints and tap target spacing.', 'open', NULL),
  ('Add Windows desktop shortcut support', 'Add launcher and deep link support for Windows app.', 'open', NULL),
  ('Add macOS keychain secure token storage', 'Store refresh tokens in macOS keychain securely.', 'open', NULL),
  ('Add Linux package post install script', 'Automate service registration after package install.', 'open', NULL),
  ('Build analytics event tracking for filters', 'Track filter usage to improve default views.', 'open', NULL),
  ('Add notification digest email scheduler', 'Send daily digest emails with grouped updates.', 'open', NULL),
  ('Fix autocomplete debounce regression', 'Resolve rapid typing bug that drops final input.', 'done', NOW() - INTERVAL '13 days'),
  ('Improve search relevance ranking for titles', 'Boost exact phrase matches over partial matches.', 'done', NOW() - INTERVAL '12 days'),
  ('Stabilize pagination when deleting records', 'Avoid duplicated and skipped rows after deletes.', 'done', NOW() - INTERVAL '11 days'),
  ('Add tag rename conflict error messaging', 'Return clear error when new tag name already exists.', 'done', NOW() - INTERVAL '10 days'),
  ('Fix done status not setting completed time', 'Ensure completed_at is always set for done tickets.', 'done', NOW() - INTERVAL '9 days'),
  ('Validate title trim and length boundaries', 'Reject empty and oversized ticket titles consistently.', 'done', NOW() - INTERVAL '8 days'),
  ('Add integration tests for tag CRUD', 'Cover create, update, list, and delete tag behaviors.', 'done', NOW() - INTERVAL '7 days'),
  ('Add integration tests for ticket list filters', 'Cover status, search, tag, and pagination combinations.', 'done', NOW() - INTERVAL '6 days'),
  ('Document API error contract examples', 'Add concrete error payload examples in docs.', 'done', NOW() - INTERVAL '5 days'),
  ('Add backup restore runbook for postgres', 'Document backup validation and restore drills.', 'done', NOW() - INTERVAL '4 days'),
  ('Implement audit trail for ticket updates', 'Track field level changes for compliance review.', 'open', NULL),
  ('Add security headers middleware', 'Set baseline security headers for API responses.', 'done', NOW() - INTERVAL '3 days'),
  ('Optimize ticket list p95 under load', 'Tune indexes and query plans for large datasets.', 'done', NOW() - INTERVAL '2 days'),
  ('Prepare Viking v1 release readiness checklist', 'Finalize readiness, rollout, and rollback plans.', 'done', NOW() - INTERVAL '1 day');

-- Map tickets to tags by title and tag name (stable even when IDs change).
WITH ticket_tag_map (ticket_title, tag_name) AS (
  VALUES
    ('Implement iOS push notification settings', 'ios'),
    ('Implement iOS push notification settings', 'mobile'),
    ('Implement iOS push notification settings', 'notifications'),

    ('Add Android offline sync retry queue', 'android'),
    ('Add Android offline sync retry queue', 'mobile'),
    ('Add Android offline sync retry queue', 'retry'),

    ('Redesign web ticket list empty state', 'web'),
    ('Redesign web ticket list empty state', 'frontend'),
    ('Redesign web ticket list empty state', 'ux'),

    ('Build autocomplete for tag selector', 'frontend'),
    ('Build autocomplete for tag selector', 'autocomplete'),
    ('Build autocomplete for tag selector', 'ux'),

    ('Optimize ticket search query with trigram index', 'backend'),
    ('Optimize ticket search query with trigram index', 'search'),
    ('Optimize ticket search query with trigram index', 'performance'),

    ('Add pagination controls to ticket list', 'frontend'),
    ('Add pagination controls to ticket list', 'pagination'),
    ('Add pagination controls to ticket list', 'filtering'),

    ('Create project Viking milestone dashboard', 'viking'),
    ('Create project Viking milestone dashboard', 'reporting'),
    ('Create project Viking milestone dashboard', 'analytics'),

    ('Integrate Odin release checklist workflow', 'odin'),
    ('Integrate Odin release checklist workflow', 'release'),
    ('Integrate Odin release checklist workflow', 'docs'),

    ('Implement Hermes webhook signature validation', 'hermes'),
    ('Implement Hermes webhook signature validation', 'api'),
    ('Implement Hermes webhook signature validation', 'security'),

    ('Add Atlas tenant onboarding wizard', 'atlas'),
    ('Add Atlas tenant onboarding wizard', 'onboarding'),
    ('Add Atlas tenant onboarding wizard', 'ux'),

    ('Improve Artemis role assignment UX', 'artemis'),
    ('Improve Artemis role assignment UX', 'authorization'),
    ('Improve Artemis role assignment UX', 'ux'),

    ('Enable CSV export for ticket reports', 'export'),
    ('Enable CSV export for ticket reports', 'reporting'),
    ('Enable CSV export for ticket reports', 'backend'),

    ('Add bulk import for legacy tickets', 'import'),
    ('Add bulk import for legacy tickets', 'backend'),
    ('Add bulk import for legacy tickets', 'postgres'),

    ('Introduce caching for tag list endpoint', 'caching'),
    ('Introduce caching for tag list endpoint', 'api'),
    ('Introduce caching for tag list endpoint', 'performance'),

    ('Add API rate limiting middleware', 'api'),
    ('Add API rate limiting middleware', 'security'),
    ('Add API rate limiting middleware', 'monitoring'),

    ('Improve accessibility for keyboard navigation', 'accessibility'),
    ('Improve accessibility for keyboard navigation', 'frontend'),
    ('Improve accessibility for keyboard navigation', 'web'),

    ('Add localization for zh-CN copy', 'localization'),
    ('Add localization for zh-CN copy', 'frontend'),
    ('Add localization for zh-CN copy', 'web'),

    ('Build dark mode theme toggle', 'dark-mode'),
    ('Build dark mode theme toggle', 'frontend'),
    ('Build dark mode theme toggle', 'ux'),

    ('Implement SSO login for enterprise users', 'authentication'),
    ('Implement SSO login for enterprise users', 'security'),
    ('Implement SSO login for enterprise users', 'api'),

    ('Add billing plan upgrade screen', 'billing'),
    ('Add billing plan upgrade screen', 'payments'),
    ('Add billing plan upgrade screen', 'frontend'),

    ('Generate monthly invoicing summary job', 'invoicing'),
    ('Generate monthly invoicing summary job', 'billing'),
    ('Generate monthly invoicing summary job', 'backend'),

    ('Add payment failure retry policy', 'payments'),
    ('Add payment failure retry policy', 'retry'),
    ('Add payment failure retry policy', 'backend'),

    ('Add structured logging for API errors', 'logging'),
    ('Add structured logging for API errors', 'api'),
    ('Add structured logging for API errors', 'backend'),

    ('Build Grafana dashboards for ticket latency', 'monitoring'),
    ('Build Grafana dashboards for ticket latency', 'observability'),
    ('Build Grafana dashboards for ticket latency', 'infra'),

    ('Harden auth token refresh flow', 'authentication'),
    ('Harden auth token refresh flow', 'security'),
    ('Harden auth token refresh flow', 'backend'),

    ('Refactor ticket service validation rules', 'refactor'),
    ('Refactor ticket service validation rules', 'backend'),
    ('Refactor ticket service validation rules', 'api'),

    ('Fix race condition in tag delete cascade', 'bug'),
    ('Fix race condition in tag delete cascade', 'backend'),
    ('Fix race condition in tag delete cascade', 'postgres'),

    ('Add E2E smoke test for ticket lifecycle', 'testing'),
    ('Add E2E smoke test for ticket lifecycle', 'ci-cd'),
    ('Add E2E smoke test for ticket lifecycle', 'frontend'),

    ('Add CI pipeline for backend lint and tests', 'ci-cd'),
    ('Add CI pipeline for backend lint and tests', 'backend'),
    ('Add CI pipeline for backend lint and tests', 'testing'),

    ('Add frontend unit tests for dialog forms', 'frontend'),
    ('Add frontend unit tests for dialog forms', 'testing'),
    ('Add frontend unit tests for dialog forms', 'ux'),

    ('Improve mobile responsive layout on dashboard', 'mobile'),
    ('Improve mobile responsive layout on dashboard', 'frontend'),
    ('Improve mobile responsive layout on dashboard', 'ux'),

    ('Add Windows desktop shortcut support', 'windows'),
    ('Add Windows desktop shortcut support', 'desktop'),
    ('Add Windows desktop shortcut support', 'frontend'),

    ('Add macOS keychain secure token storage', 'macos'),
    ('Add macOS keychain secure token storage', 'desktop'),
    ('Add macOS keychain secure token storage', 'security'),

    ('Add Linux package post install script', 'linux'),
    ('Add Linux package post install script', 'infra'),
    ('Add Linux package post install script', 'docs'),

    ('Build analytics event tracking for filters', 'analytics'),
    ('Build analytics event tracking for filters', 'filtering'),
    ('Build analytics event tracking for filters', 'frontend'),

    ('Add notification digest email scheduler', 'notifications'),
    ('Add notification digest email scheduler', 'backend'),
    ('Add notification digest email scheduler', 'retry'),

    ('Fix autocomplete debounce regression', 'bug'),
    ('Fix autocomplete debounce regression', 'autocomplete'),
    ('Fix autocomplete debounce regression', 'frontend'),

    ('Improve search relevance ranking for titles', 'search'),
    ('Improve search relevance ranking for titles', 'performance'),
    ('Improve search relevance ranking for titles', 'backend'),

    ('Stabilize pagination when deleting records', 'pagination'),
    ('Stabilize pagination when deleting records', 'bug'),
    ('Stabilize pagination when deleting records', 'frontend'),

    ('Add tag rename conflict error messaging', 'bug'),
    ('Add tag rename conflict error messaging', 'ux'),
    ('Add tag rename conflict error messaging', 'api'),

    ('Fix done status not setting completed time', 'bug'),
    ('Fix done status not setting completed time', 'backend'),
    ('Fix done status not setting completed time', 'api'),

    ('Validate title trim and length boundaries', 'testing'),
    ('Validate title trim and length boundaries', 'api'),
    ('Validate title trim and length boundaries', 'backend'),

    ('Add integration tests for tag CRUD', 'testing'),
    ('Add integration tests for tag CRUD', 'api'),
    ('Add integration tests for tag CRUD', 'backend'),

    ('Add integration tests for ticket list filters', 'testing'),
    ('Add integration tests for ticket list filters', 'filtering'),
    ('Add integration tests for ticket list filters', 'pagination'),

    ('Document API error contract examples', 'docs'),
    ('Document API error contract examples', 'api'),
    ('Document API error contract examples', 'testing'),

    ('Add backup restore runbook for postgres', 'postgres'),
    ('Add backup restore runbook for postgres', 'infra'),
    ('Add backup restore runbook for postgres', 'docs'),

    ('Implement audit trail for ticket updates', 'security'),
    ('Implement audit trail for ticket updates', 'logging'),
    ('Implement audit trail for ticket updates', 'backend'),

    ('Add security headers middleware', 'security'),
    ('Add security headers middleware', 'api'),
    ('Add security headers middleware', 'infra'),

    ('Optimize ticket list p95 under load', 'performance'),
    ('Optimize ticket list p95 under load', 'postgres'),
    ('Optimize ticket list p95 under load', 'observability'),

    ('Prepare Viking v1 release readiness checklist', 'viking'),
    ('Prepare Viking v1 release readiness checklist', 'release'),
    ('Prepare Viking v1 release readiness checklist', 'docs')
)
INSERT INTO ticket_tags (ticket_id, tag_id)
SELECT t.id, tg.id
FROM ticket_tag_map m
JOIN tickets t ON t.title = m.ticket_title
JOIN tags tg ON tg.name = m.tag_name
ON CONFLICT DO NOTHING;

COMMIT;

-- Quick verification checks.
SELECT COUNT(*) AS ticket_count FROM tickets;
SELECT COUNT(*) AS tag_count FROM tags;
SELECT COUNT(*) AS ticket_tag_count FROM ticket_tags;
