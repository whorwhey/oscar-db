-- Database schema for the Academy Awards (Oscars) 
-- Design rationale: schema.md, data_notes.md
-- Designed for SQLite3, but should be compatible with other RDBMS with minor adjustments.
-- Tables: ceremonies, categories, films, people, nominations,
--         nomination_films, nomination_people, film_directors
-- NOTE: run PRAGMA foreign_keys = ON; in every connection

CREATE TABLE ceremonies (
    ceremony INTEGER PRIMARY KEY,   -- ordinal, 98th for year 2026
    year_label TEXT NOT NULL        -- e.g. "2026" "1927/1928"
);

CREATE TABLE categories (
    category_id  INTEGER PRIMARY KEY,
    source_name  TEXT NOT NULL UNIQUE,  -- exact CanonicalCategory string in the
                                        -- DLu dataset; join key for ingestion.
                                        -- Merged across years but still historical
                                        -- (e.g. SOUND RECORDING), not modern.
    award_group  TEXT NOT NULL,         -- official-site facet, curated by us
    class        TEXT NOT NULL          -- coarse group, curated by us (8 values)
);

CREATE TABLE films (
    film_id INTEGER PRIMARY KEY,    -- unique identifier
    title TEXT NOT NULL,            -- e.g. "Everything Everywhere All At Once"
    title_zh TEXT,                  -- zh-Hans; enrichment later e.g. "瞬息全宇宙"
    imdb_id TEXT UNIQUE,            -- e.g. "tt1630029"
    douban_id TEXT UNIQUE,          -- enrichment later e.g. "34978685"
    release_year INTEGER,           -- IMDb startYear e.g. 2022
    original_title TEXT,            -- IMDb originalTitle, verbatim; NULL = unknown
    runtime_minutes INTEGER         -- IMDb runtimeMinutes; NULL = unknown
);

CREATE TABLE people (
    person_id INTEGER PRIMARY KEY,   -- unique identifier
    name TEXT NOT NULL,              -- e.g. "Michelle Yeoh"
    name_zh TEXT,                    -- zh-Hans; enrichment later e.g. "杨紫琼"
    imdb_id TEXT UNIQUE,             -- e.g. "nm0941777"
    douban_id TEXT UNIQUE,           -- enrichment later e.g. "1048021"
    kind TEXT NOT NULL CHECK (kind IN ('person', 'company')),
    birth_year INTEGER,              -- IMDb birthYear; NULL = unknown
    death_year INTEGER               -- IMDb deathYear; NULL = unknown or alive
);

CREATE TABLE nominations (
    nomination_id INTEGER PRIMARY KEY,   -- unique identifier
    ceremony INTEGER NOT NULL REFERENCES ceremonies(ceremony),
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    raw_category TEXT NOT NULL,          -- category name as written that year
    official_name TEXT,                  -- official name as written from source
    is_winner INTEGER NOT NULL DEFAULT 0 CHECK (is_winner IN (0, 1)),
    detail TEXT, 
    note TEXT, 
    citation TEXT
);

CREATE TABLE nomination_films (     -- junction table between nominations and films
    nomination_id INTEGER NOT NULL REFERENCES nominations(nomination_id),
    film_id INTEGER NOT NULL REFERENCES films(film_id),
    PRIMARY KEY (nomination_id, film_id)
);

CREATE TABLE nomination_people (    -- junction table between nominations and people
    nomination_id INTEGER NOT NULL REFERENCES nominations(nomination_id),
    person_id INTEGER NOT NULL REFERENCES people(person_id),
    PRIMARY KEY (nomination_id, person_id)
);

CREATE TABLE film_directors (   -- junction table between films and directing people
    film_id INTEGER NOT NULL REFERENCES films(film_id),
    person_id INTEGER NOT NULL REFERENCES people(person_id),
    PRIMARY KEY (film_id, person_id)
);
