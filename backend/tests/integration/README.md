# Integration Tests

The live M2 test is collected but always skipped unless
`--run-provider-integration` is passed. It additionally requires an API key, approved
public wallet/window/quote inputs, and explicit request and credit ceilings through
the `ENTRYGLASS_INTEGRATION_*` variables listed in the test. CI and `make test` never
pass the flag, so ordinary runs cannot spend credits.

The test writes only to pytest's temporary private SQLite directory and does not
print provider rows. Keep private provider responses out of version control and use
clearly synthetic fixtures for public contract tests.
