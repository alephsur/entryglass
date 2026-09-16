# Integration Tests

Reserved for explicitly opt-in provider checks. No live integration test is part of
pytest or CI. Use the bounded validation command documented in
`docs/PROVIDER_VALIDATION.md` for the current M1 check. Keep private provider
responses out of version control and use clearly synthetic fixtures for public
contract tests.
