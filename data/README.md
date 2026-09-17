# Private Local Data

Local SQLite files and permitted private evidence are stored here by explicit tools.
The M2 importer defaults to `data/entryglass.sqlite3` and creates it with owner-only
permissions. Contents other than this README are ignored by Git. This is not
encrypted storage; decide retention, backup, and deletion policies before use.
Never commit API keys, raw provider payloads, or restricted labeled-wallet lists.
