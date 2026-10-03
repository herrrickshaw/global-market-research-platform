-- services/schema.sql — the pipeline handoff bus.
--
-- WHY A TABLE AND NOT A BROKER. The coupling being fixed is one-directional and
-- daily: collector -> scoring -> delivery, one producer and one consumer per
-- hop. Redis or RabbitMQ would add a service to run, monitor and back up in
-- exchange for semantics this workload never uses (fan-out, partitions,
-- consumer groups). Postgres is already here, already backed up nightly to two
-- clouds, and already the thing every stage can reach.
--
-- WHAT IT ACTUALLY FIXES. On 2026-08-15 the 06:30 send phase blocked on a lock
-- held by an over-running 03:00 data phase, exited 0, and no brief went out
-- with nothing reporting it. The stages were coupled by a MUTEX, so a slow
-- upstream could silently starve a downstream with a hard deadline.
--
-- Here a stage never waits on its upstream. It asks for the newest artifact
-- that PASSED, decides for itself whether that is fresh enough, and records what
-- it chose. A late collector then degrades to "delivery sent using yesterday's
-- scores, and said so" instead of "no brief, no error".

CREATE SCHEMA IF NOT EXISTS pipeline;

CREATE TABLE IF NOT EXISTS pipeline.events (
    id           bigserial PRIMARY KEY,
    stage        text        NOT NULL,   -- collector | scoring | delivery | serving
    run_id       text        NOT NULL,   -- groups one logical pass through the chain
    status       text        NOT NULL,   -- ok | failed | degraded
    artifact     text,                   -- what it produced (path, table, message-id)
    rows         bigint,                 -- size of that artifact, for sanity checks
    -- 🔴 asof is the DATA's date, not the run's. A stage that reprocesses an old
    -- day must not look newer than one that processed today: that conflation is
    -- how snapshot_market nearly recorded 17-day-old prices as a fresh
    -- observation (E-021).
    asof         date        NOT NULL,
    detail       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- The only hot query: "newest passing artifact from stage X".
CREATE INDEX IF NOT EXISTS events_stage_ok_idx
    ON pipeline.events (stage, asof DESC, created_at DESC)
    WHERE status = 'ok';

CREATE INDEX IF NOT EXISTS events_run_idx ON pipeline.events (run_id);
