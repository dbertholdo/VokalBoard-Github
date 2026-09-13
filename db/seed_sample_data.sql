-- ============================================================
-- Dados de exemplo (opcional) — útil para praticar SELECTs,
-- JOINs e filtros assim que o app estiver no ar.
--
-- Senha de todos os usuários de exemplo: "senha123"
-- (hash gerado com bcrypt — ver app/auth.py)
-- ============================================================

INSERT INTO users (email, password_hash, full_name, role, city, phone, email_verified) VALUES
('sofia.soprano@example.com', '$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Sofia Klein', 'singer', 'München', '+49 170 1111111', TRUE),
('tobias.tenor@example.com',  '$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Tobias Wagner', 'singer', 'Berlin', '+49 170 2222222', TRUE),
('anna.dirigentin@example.com','$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Anna Hoffmann', 'conductor', 'Hamburg', '+49 170 3333333', TRUE),
('markus.dirigent@example.com','$2b$12$eODS5GpUFdXCjrrUVdHjduVizFFbR2u01HBCMhimWHLgRfWrSULFK', 'Markus Schulz', 'conductor', 'München', '+49 170 4444444', TRUE);

INSERT INTO singer_profiles (user_id, voice_type_id, fach, bio, experience_years)
SELECT id, (SELECT id FROM voice_types WHERE name = 'Soprano'), 'Lyric Soprano',
       'Cantora lírica com experiência em ópera e oratório.', 6
FROM users WHERE email = 'sofia.soprano@example.com';

INSERT INTO singer_profiles (user_id, voice_type_id, fach, bio, experience_years)
SELECT id, (SELECT id FROM voice_types WHERE name = 'Tenor'), 'Spieltenor',
       'Tenor com foco em repertório barroco e contemporâneo.', 4
FROM users WHERE email = 'tobias.tenor@example.com';

-- Links de Audiobeispiel (até 3 por cantor(a))
INSERT INTO singer_audio_links (user_id, url)
SELECT id, url FROM users, unnest(ARRAY[
    'https://www.youtube.com/watch?v=example_sofia_1',
    'https://soundcloud.com/example/sofia-mozart-aria'
]) AS url
WHERE email = 'sofia.soprano@example.com';

INSERT INTO singer_audio_links (user_id, url)
SELECT id, 'https://www.youtube.com/watch?v=example_tobias_1'
FROM users WHERE email = 'tobias.tenor@example.com';

-- Redes sociais (opcional, até uma por plataforma)
INSERT INTO user_social_links (user_id, platform, url)
SELECT id, 'instagram', 'https://instagram.com/sofia.soprano.example'
FROM users WHERE email = 'sofia.soprano@example.com';

INSERT INTO user_social_links (user_id, platform, url)
SELECT id, 'website', 'https://hamburger-kammerchor.example.com'
FROM users WHERE email = 'anna.dirigentin@example.com';

INSERT INTO conductor_profiles (user_id, ensemble_name, bio, experience_years, website_url)
SELECT id, 'Hamburger Kammerchor', 'Regente de coro com 10 anos de experiência em música sacra.', 10, 'https://example.com/anna'
FROM users WHERE email = 'anna.dirigentin@example.com';

INSERT INTO conductor_profiles (user_id, ensemble_name, bio, experience_years, website_url)
SELECT id, NULL, 'Maestro convidado, especializado em ópera romântica.', 15, NULL
FROM users WHERE email = 'markus.dirigent@example.com';

-- Hashtags de compositores (até 10 por cantor)
INSERT INTO singer_composer_tags (user_id, tag)
SELECT id, tag FROM users, unnest(ARRAY['Mozart', 'Verdi', 'Puccini']) AS tag
WHERE email = 'sofia.soprano@example.com';

INSERT INTO singer_composer_tags (user_id, tag)
SELECT id, tag FROM users, unnest(ARRAY['Bach', 'Handel', 'Britten']) AS tag
WHERE email = 'tobias.tenor@example.com';

INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
SELECT id, 'seeking_singer', 'Procuro soprano para Requiem de Mozart',
       'Coro busca soprano solista para apresentação em dezembro. Ensaios às terças.',
       'Hamburg', 'Hamburg', (SELECT id FROM voice_types WHERE name = 'Soprano'), 'Mozart, Requiem',
       'St. Michaelis Kirche', '250€', 'solo', '2026-12-05'
FROM users WHERE email = 'anna.dirigentin@example.com';

INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, event_date)
SELECT id, 'singer_available', 'Tenor disponível para audições em Berlin/München',
       'Tenor com repertório barroco e romântico disponível para audições e substituições.',
       'Berlin', 'Berlin', (SELECT id FROM voice_types WHERE name = 'Tenor'), 'Barroco, Romântico', NULL
FROM users WHERE email = 'tobias.tenor@example.com';

INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, ensemble_type, event_date)
SELECT id, 'seeking_conductor', 'Grupo vocal busca regente para temporada 2027',
       'Grupo vocal amador busca maestro(a) para ensaios semanais e 2 concertos por ano.',
       'München', 'Bayern', NULL, 'A definir', 'choir', NULL
FROM users WHERE email = 'sofia.soprano@example.com';

-- Exemplo de cantor(a) postando uma vaga (procurando outro cantor para o seu recital)
INSERT INTO listings (author_id, listing_type, title, description, city, state, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
SELECT id, 'seeking_singer', 'Procuro baixo para recital a dois',
       'Monto um recital de duetos e preciso de um baixo para completar o programa.',
       'Berlin', 'Berlin', (SELECT id FROM voice_types WHERE name = 'Baixo'), 'Schubert, Lieder',
       'Kammermusiksaal', 'a combinar', 'solo', NULL
FROM users WHERE email = 'tobias.tenor@example.com';

-- Exemplo fora da Alemanha, para testar o filtro de país (Áustria)
INSERT INTO listings (author_id, listing_type, title, description, city, state, country, voice_type_id, repertoire, venue, fee, ensemble_type, event_date)
SELECT id, 'seeking_singer', 'Alt gesucht für Weihnachtskonzert in Wien',
       'Kirchenchor sucht Altstimme für Konzert am 4. Advent.',
       'Wien', 'Wien', 'AT', (SELECT id FROM voice_types WHERE name = 'Alto'), 'Weihnachtsoratorium',
       'Stephansdom', '180€', 'solo', '2026-12-20'
FROM users WHERE email = 'anna.dirigentin@example.com';
