-- recovery-agent owns only this database. Idempotent: applied on every startup.

-- Every Kafka record the observer has seen. (topic, partition, offset) is the identity:
-- redelivery after a crash re-inserts the same key and is ignored.
CREATE TABLE IF NOT EXISTS event_log (
    id               BIGSERIAL    PRIMARY KEY,
    topic            TEXT         NOT NULL,
    kafka_partition  INT          NOT NULL,
    kafka_offset     BIGINT       NOT NULL,
    order_id         INT,
    event_timestamp  TIMESTAMPTZ,
    payload          JSONB        NOT NULL,
    observed_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (topic, kafka_partition, kafka_offset)
);
CREATE INDEX IF NOT EXISTS idx_event_log_order ON event_log (order_id);

-- When observation of each partition began. Events older than this were never observed,
-- so "no event in event_log" only means "not seen", and only for events after observed_since.
CREATE TABLE IF NOT EXISTS observer_partition (
    consumer_group   TEXT         NOT NULL,
    topic            TEXT         NOT NULL,
    kafka_partition  INT          NOT NULL,
    first_offset     BIGINT       NOT NULL,
    observed_since   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer_group, topic, kafka_partition)
);

-- Immutable snapshot of everything an investigation was based on.
CREATE TABLE IF NOT EXISTS investigation_input (
    id            UUID         PRIMARY KEY,
    order_id      INT          NOT NULL,
    requested_by  TEXT         NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    evidence_ids  TEXT[]       NOT NULL,
    snapshot      JSONB        NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_investigation_input_order ON investigation_input (order_id);

-- One read-only investigation: the returned result plus everything needed to audit or score it
CREATE TABLE IF NOT EXISTS investigation (
    id            UUID         PRIMARY KEY,
    input_id      UUID         NOT NULL REFERENCES investigation_input (id),
    order_id      INT          NOT NULL,
    concern       TEXT         NOT NULL,
    requested_by  TEXT         NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finding       TEXT         NOT NULL,
    model_used    BOOLEAN      NOT NULL,
    result        JSONB        NOT NULL,
    trace         JSONB        NOT NULL,
    latency_ms    INT          NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_investigation_order ON investigation (order_id);
