ALTER TABLE site_banners ADD COLUMN IF NOT EXISTS voice_type_id INTEGER REFERENCES voice_types(id);
