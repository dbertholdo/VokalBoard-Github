-- Apply transactionally before deploying the corresponding application code.
BEGIN;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS available_from date;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS available_until date;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE listings ALTER COLUMN country DROP NOT NULL;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS activity_at timestamptz;
UPDATE messages SET activity_at=created_at WHERE activity_at IS NULL;
-- A conversation is the pair of participants, irrespective of listing.
WITH activity AS (
 SELECT least(sender_id,recipient_id) a, greatest(sender_id,recipient_id) b, max(created_at) latest
 FROM messages WHERE archived_at IS NULL GROUP BY 1,2
)
UPDATE messages m SET activity_at=a.latest FROM activity a
WHERE least(m.sender_id,m.recipient_id)=a.a AND greatest(m.sender_id,m.recipient_id)=a.b
  AND m.archived_at IS NULL;
ALTER TABLE messages ALTER COLUMN activity_at SET DEFAULT now();
ALTER TABLE messages ALTER COLUMN activity_at SET NOT NULL;

CREATE TABLE IF NOT EXISTS content_lifecycle_log (
 id bigserial PRIMARY KEY, entity_type text NOT NULL, entity_id bigint NOT NULL,
 action text NOT NULL, actor_id bigint, occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lifecycle_entity ON content_lifecycle_log(entity_type,entity_id);
CREATE INDEX IF NOT EXISTS idx_messages_pair_activity ON messages(least(sender_id,recipient_id),greatest(sender_id,recipient_id),activity_at);

ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS listing_snapshot jsonb;
UPDATE job_matches m SET listing_snapshot=jsonb_build_object('title',l.title,'event_date',l.event_date,'fee',l.fee)
FROM listings l WHERE l.id=m.listing_id AND m.listing_snapshot IS NULL;
ALTER TABLE job_matches ALTER COLUMN listing_id DROP NOT NULL;
ALTER TABLE job_matches ALTER COLUMN vacancy_id DROP NOT NULL;
ALTER TABLE job_matches DROP CONSTRAINT IF EXISTS job_matches_listing_id_fkey;
ALTER TABLE job_matches ADD CONSTRAINT job_matches_listing_id_fkey FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE SET NULL;
ALTER TABLE job_matches DROP CONSTRAINT IF EXISTS job_matches_vacancy_id_fkey;
ALTER TABLE job_matches ADD CONSTRAINT job_matches_vacancy_id_fkey FOREIGN KEY(vacancy_id) REFERENCES listing_vacancies(id) ON DELETE SET NULL;

CREATE OR REPLACE FUNCTION snapshot_match_listing() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 SELECT jsonb_build_object('title',title,'event_date',event_date,'fee',fee)
 INTO NEW.listing_snapshot FROM listings WHERE id=NEW.listing_id;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS match_snapshot ON job_matches;
CREATE TRIGGER match_snapshot BEFORE INSERT ON job_matches FOR EACH ROW EXECUTE FUNCTION snapshot_match_listing();

CREATE OR REPLACE VIEW visible_listings AS
 SELECT * FROM listings WHERE archived_at IS NULL AND deleted_at IS NULL
 AND (COALESCE(available_until,event_date) IS NULL OR COALESCE(available_until,event_date)+30 > CURRENT_DATE);
CREATE OR REPLACE VIEW visible_messages AS
 SELECT * FROM messages WHERE archived_at IS NULL AND activity_at+interval '30 days' > now();

CREATE OR REPLACE FUNCTION validate_availability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.archived_at IS NOT NULL OR NEW.deleted_at IS NOT NULL THEN RETURN NEW; END IF;
 IF NEW.listing_type='singer_available' THEN
   IF NEW.available_from IS NULL OR NEW.available_until IS NULL OR
      NEW.available_until < NEW.available_from OR NEW.available_until-NEW.available_from > 29 THEN
     RAISE EXCEPTION 'availability_invalid' USING ERRCODE='23514';
   END IF;
   -- Per-owner transaction lock protects the quota even under concurrent requests.
   PERFORM pg_advisory_xact_lock(8201, (NEW.author_id % 2147483647)::integer);
   IF NEW.is_active AND NEW.available_until >= CURRENT_DATE AND
      (SELECT count(*) FROM listings WHERE author_id=NEW.author_id AND id<>NEW.id
        AND listing_type='singer_available' AND is_active AND archived_at IS NULL
        AND deleted_at IS NULL AND available_until>=CURRENT_DATE) >= 2 THEN
     RAISE EXCEPTION 'availability_limit' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS availability_guard ON listings;
CREATE TRIGGER availability_guard BEFORE INSERT OR UPDATE ON listings FOR EACH ROW EXECUTE FUNCTION validate_availability();

CREATE OR REPLACE FUNCTION message_activity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock((least(NEW.sender_id,NEW.recipient_id)%2147483647)::integer,
                              (greatest(NEW.sender_id,NEW.recipient_id)%2147483647)::integer);
 -- Expired history never returns when a new conversation starts.
 UPDATE messages SET archived_at=activity_at+interval '30 days'
 WHERE archived_at IS NULL AND activity_at+interval '30 days'<=now()
 AND least(sender_id,recipient_id)=least(NEW.sender_id,NEW.recipient_id)
 AND greatest(sender_id,recipient_id)=greatest(NEW.sender_id,NEW.recipient_id);
 UPDATE messages SET activity_at=NEW.created_at
 WHERE archived_at IS NULL AND least(sender_id,recipient_id)=least(NEW.sender_id,NEW.recipient_id)
 AND greatest(sender_id,recipient_id)=greatest(NEW.sender_id,NEW.recipient_id);
 NEW.activity_at=NEW.created_at;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS conversation_activity ON messages;
CREATE TRIGGER conversation_activity BEFORE INSERT ON messages FOR EACH ROW EXECUTE FUNCTION message_activity();

CREATE OR REPLACE FUNCTION audit_content_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor bigint; event text;
BEGIN
 IF TG_OP='DELETE' THEN
   INSERT INTO content_lifecycle_log(entity_type,entity_id,action) VALUES(TG_TABLE_NAME,OLD.id,'purged');
   RETURN OLD;
 END IF;
 actor=COALESCE((to_jsonb(NEW)->>'author_id')::bigint,(to_jsonb(NEW)->>'sender_id')::bigint);
 IF TG_OP='INSERT' THEN event='posted';
 ELSIF OLD.deleted_at IS DISTINCT FROM NEW.deleted_at THEN event='deleted';
 ELSE RETURN NEW;
 END IF;
 INSERT INTO content_lifecycle_log(entity_type,entity_id,action,actor_id) VALUES(TG_TABLE_NAME,NEW.id,event,actor);
 RETURN NEW;
END $$;
-- Separate UPDATE logic works for messages (which have no deleted_at).
CREATE OR REPLACE FUNCTION audit_content_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (to_jsonb(OLD)->>'deleted_at') IS NULL AND (to_jsonb(NEW)->>'deleted_at') IS NOT NULL THEN
   INSERT INTO content_lifecycle_log(entity_type,entity_id,action) VALUES(TG_TABLE_NAME,NEW.id,'deleted');
 END IF;
 IF OLD.archived_at IS NULL AND NEW.archived_at IS NOT NULL THEN
   INSERT INTO content_lifecycle_log(entity_type,entity_id,action) VALUES(TG_TABLE_NAME,NEW.id,'archived');
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS listing_audit ON listings;
CREATE TRIGGER listing_audit AFTER INSERT OR DELETE ON listings FOR EACH ROW EXECUTE FUNCTION audit_content_lifecycle();
DROP TRIGGER IF EXISTS listing_change_audit ON listings;
CREATE TRIGGER listing_change_audit AFTER UPDATE ON listings FOR EACH ROW EXECUTE FUNCTION audit_content_change();
DROP TRIGGER IF EXISTS message_audit ON messages;
CREATE TRIGGER message_audit AFTER INSERT OR DELETE ON messages FOR EACH ROW EXECUTE FUNCTION audit_content_lifecycle();
DROP TRIGGER IF EXISTS message_change_audit ON messages;
CREATE TRIGGER message_change_audit AFTER UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION audit_content_change();
COMMIT;
