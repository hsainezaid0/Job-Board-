PRAGMA foreign_keys = ON;

CREATE TABLE
    IF NOT EXISTS people (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        phone TEXT NOT NULL DEFAULT '',
        password_hash TEXT,
        role TEXT NOT NULL DEFAULT 'candidate' CHECK (role IN ('candidate', 'admin', 'company_admin')),
        company_id INTEGER REFERENCES companies(id) ON DELETE RESTRICT,
        created_at TEXT NOT NULL DEFAULT (strftime ('%Y-%m-%dT%H:%M:%SZ', 'now')),
        CHECK ((role = 'company_admin' AND company_id IS NOT NULL) OR (role <> 'company_admin' AND company_id IS NULL))
    );

CREATE TABLE
    IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        industry TEXT NOT NULL,
        location TEXT NOT NULL,
        website TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#355d50',
        created_at TEXT NOT NULL DEFAULT (strftime ('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );

CREATE TABLE
    IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);

CREATE TABLE
    IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
        category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
        contact_id INTEGER NOT NULL REFERENCES people (id) ON DELETE RESTRICT,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        description TEXT NOT NULL,
        requirements TEXT NOT NULL,
        location TEXT NOT NULL,
        contract TEXT NOT NULL CHECK (
            contract IN ('CDI', 'CDD', 'Stage', 'Alternance', 'Freelance')
        ),
        work_mode TEXT NOT NULL CHECK (
            work_mode IN ('Hybride', 'Sur site', 'Télétravail')
        ),
        salary_min INTEGER NOT NULL CHECK (salary_min >= 0),
        salary_max INTEGER NOT NULL CHECK (salary_max >= salary_min),
        working_time TEXT NOT NULL DEFAULT 'Temps plein',
        featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (strftime ('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );

CREATE TABLE
    IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY,
        ad_id INTEGER NOT NULL REFERENCES ads (id) ON DELETE CASCADE,
        person_id INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Reçue' CHECK (
            status IN (
                'Reçue',
                'En cours',
                'Entretien',
                'Acceptée',
                'Refusée'
            )
        ),
        email_status TEXT NOT NULL DEFAULT 'Enregistré',
        created_at TEXT NOT NULL DEFAULT (strftime ('%Y-%m-%dT%H:%M:%SZ', 'now')),
        UNIQUE (ad_id, person_id)
    );

CREATE TABLE
    IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        person_id INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
        expires_at INTEGER NOT NULL
    );

CREATE INDEX IF NOT EXISTS idx_ads_company ON ads (company_id);

CREATE INDEX IF NOT EXISTS idx_ads_category ON ads (category_id);

CREATE INDEX IF NOT EXISTS idx_applications_person ON applications (person_id);

CREATE INDEX IF NOT EXISTS idx_applications_ad ON applications (ad_id);