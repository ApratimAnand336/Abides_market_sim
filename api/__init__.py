"""FinVerse dashboard backend: simulation runner, payload export and HTTP API."""

SCHEMA_VERSION = "1.2"  # v1.3: payload.realism and payload.oracle_events

# Engine (agent model) version, part of the run cache key via
# jobs.engine_version(). Bump it whenever agent behaviour changes so cached
# runs from older engines are never reused.
ENGINE_VERSION = "1.3"
