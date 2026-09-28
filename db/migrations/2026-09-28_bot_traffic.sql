-- Bot traffic kept out of Analytics (2026-09-28, HANDOFF 3b). Idempotent, no $$.
-- Apply with psql. Until it runs, bot requests are simply not recorded
-- (app/traffic.py checks for the table); human visits work either way.
CREATE TABLE IF NOT EXISTS bot_traffic_daily (
    day       DATE NOT NULL,
    bot_name  VARCHAR(60) NOT NULL,
    hits      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, bot_name)
);
