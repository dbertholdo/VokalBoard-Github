-- ============================================================
-- Sample data (optional) — useful for practicing SELECTs,
-- JOINs and filters as soon as the app is up and running.
--
-- Password for all sample users: "senha123"
-- (hash generated with bcrypt — see app/auth.py)
-- ============================================================

INSERT INTO users (email, password_hash, full_name, role, city, phone, email_verified) VALUES
('sofia.soprano@example.com', '$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Sofia Klein', 'singer', 'München', '+49 170 1111111', TRUE),
('tobias.tenor@example.com',  '$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Tobias Wagner', 'singer', 'Berlin', '+49 170 2222222', TRUE),
('anna.dirigentin@example.com','$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Anna Hoffmann', 'conductor', 'Hamburg', '+49 170 3333333', TRUE),
('markus.dirigent@example.com','$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Markus Schulz', 'conductor', 'München', '+49 170 4444444', TRUE);

INSERT INTO singer_profiles (user_id, voice_type_id, fach, bio, experience_years)
SELECT id, (SELECT id FROM voice_types WHERE name = 'Soprano'), 'Lyric Soprano',
       'Lyric singer with experience in opera and oratorio.', 6
FROM users WHERE email = 'sofia.soprano@example.com';

INSERT INTO singer_profiles (user_id, voice_type_id, fach, bio, experience_years)
SELECT id, (SELECT id FROM voice_types WHERE name = 'Tenor'), 'Spieltenor',
       'Tenor focused on baroque and contemporary repertoire.', 4
FROM users WHERE email = 'tobias.tenor@example.com';

-- Audio sample links (up to 3 per singer)
INSERT INTO singer_audio_links (user_id, url)
SELECT id, url FROM users, unnest(ARRAY[
    'https://www.youtube.com/watch?v=example_sofia_1',
    'https://soundcloud.com/example/sofia-mozart-aria'
]) AS url
WHERE email = 'sofia.soprano@example.com';

INSERT INTO singer_audio_links (user_id, url)
SELECT id, 'https://www.youtube.com/watch?v=example_tobias_1'
FROM users WHERE email = 'tobias.tenor@example.com';

-- Social links (optional, up to one per platform)
INSERT INTO user_social_links (user_id, platform, url)
SELECT id, 'instagram', 'https://instagram.com/sofia.soprano.example'
FROM users WHERE email = 'sofia.soprano@example.com';

INSERT INTO user_social_links (user_id, platform, url)
SELECT id, 'website', 'https://hamburger-kammerchor.example.com'
FROM users WHERE email = 'anna.dirigentin@example.com';

INSERT INTO conductor_profiles (user_id, ensemble_name, bio, experience_years, website_url)
SELECT id, 'Hamburger Kammerchor', 'Choir conductor with 10 years of experience in sacred music.', 10, 'https://example.com/anna'
FROM users WHERE email = 'anna.dirigentin@example.com';

INSERT INTO conductor_profiles (user_id, ensemble_name, bio, experience_years, website_url)
SELECT id, NULL, 'Guest conductor, specialized in romantic opera.', 15, NULL
FROM users WHERE email = 'markus.dirigent@example.com';

-- Composer hashtags (up to 10 per singer)
INSERT INTO singer_composer_tags (user_id, tag)
SELECT id, tag FROM users, unnest(ARRAY['Mozart', 'Verdi', 'Puccini']) AS tag
WHERE email = 'sofia.soprano@example.com';

INSERT INTO singer_composer_tags (user_id, tag)
SELECT id, tag FROM users, unnest(ARRAY['Bach', 'Handel', 'Britten']) AS tag
WHERE email = 'tobias.tenor@example.com';

INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
SELECT id, 'seeking_singer', 'Looking for a soprano for Mozart''s Requiem',
       'Choir looking for a solo soprano for a December performance. Rehearsals on Tuesdays.',
       'Hamburg', 'Hamburg', (SELECT id FROM voice_types WHERE name = 'Soprano'), 'Mozart, Requiem',
       'St. Michaelis Kirche', '250€', 'solo', '2026-12-05'
FROM users WHERE email = 'anna.dirigentin@example.com';

INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, event_date)
SELECT id, 'singer_available', 'Tenor available for auditions in Berlin/München',
       'Tenor with baroque and romantic repertoire available for auditions and substitutions.',
       'Berlin', 'Berlin', (SELECT id FROM voice_types WHERE name = 'Tenor'), 'Baroque, Romantic', NULL
FROM users WHERE email = 'tobias.tenor@example.com';

INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, ensemble_type, event_date)
SELECT id, 'seeking_conductor', 'Vocal group looking for a conductor for the 2027 season',
       'Amateur vocal group looking for a conductor for weekly rehearsals and 2 concerts per year.',
       'München', 'Bayern', NULL, 'To be defined', 'choir', NULL
FROM users WHERE email = 'sofia.soprano@example.com';

-- Example of a singer posting a listing (looking for another singer for their recital)
INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
SELECT id, 'seeking_singer', 'Looking for a bass for a duo recital',
       'Putting together a recital of duets and need a bass to complete the program.',
       'Berlin', 'Berlin', (SELECT id FROM voice_types WHERE name = 'Bass'), 'Schubert, Lieder',
       'Kammermusiksaal', 'a combinar', 'solo', NULL
FROM users WHERE email = 'tobias.tenor@example.com';

-- Example outside Germany, to test the country filter (Austria)
INSERT INTO listings (author_id, listing_type, title, description, city, state, country, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
SELECT id, 'seeking_singer', 'Alt gesucht für Weihnachtskonzert in Wien',
       'Kirchenchor sucht Altstimme für Konzert am 4. Advent.',
       'Wien', 'Wien', 'AT', (SELECT id FROM voice_types WHERE name = 'Alto'), 'Weihnachtsoratorium',
       'Stephansdom', '180€', 'solo', '2026-12-20'
FROM users WHERE email = 'anna.dirigentin@example.com';
