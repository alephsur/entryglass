# Integration Tests

Reserved for explicitly opt-in provider checks. No live integration tests exist.
Future tests must require a deliberate flag and a configured budget; they must not
run during ordinary pytest or CI execution. Keep private provider responses out of
version control and use clearly synthetic fixtures for public contract tests.
