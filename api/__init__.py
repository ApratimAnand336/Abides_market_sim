"""FinVerse dashboard backend: simulation runner, payload export and HTTP API."""

SCHEMA_VERSION = "1.1"

# Engine (agent model) version, part of the run cache key via
# jobs.engine_version(). Bump it whenever agent behaviour changes so cached
# runs from older engines are never reused.
ENGINE_VERSION = "1.1"
