#!/bin/ash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE TABLE IF NOT EXISTS public.hk_record
    (
        record_id serial NOT NULL,
        hk_type text COLLATE pg_catalog."default" NOT NULL,
        hk_source text COLLATE pg_catalog."default" NOT NULL,
        source_version text COLLATE pg_catalog."default",
        device text COLLATE pg_catalog."default",
        creation_date timestamp with time zone,
        start_date timestamp with time zone NOT NULL,
        end_date timestamp with time zone NOT NULL,
        unit text COLLATE pg_catalog."default",
        hk_value double precision,
        CONSTRAINT hk_record_pkey PRIMARY KEY (record_id)
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_record
        OWNER to $POSTGRES_USER;

    CREATE TABLE IF NOT EXISTS public.hk_person
    (
        person_id serial NOT NULL,
        fullname text COLLATE pg_catalog."default",
        firstname text COLLATE pg_catalog."default",
        lastname text COLLATE pg_catalog."default",
        dob date NOT NULL,
        biological_sex text COLLATE pg_catalog."default",
        gender text COLLATE pg_catalog."default",
        blood_type text COLLATE pg_catalog."default",
        fitzpatrick_skin_typ text COLLATE pg_catalog."default",
        CONSTRAINT hk_person_pkey PRIMARY KEY (person_id)
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_person
        OWNER to $POSTGRES_USER;
EOSQL
