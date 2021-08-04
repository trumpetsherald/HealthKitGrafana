#!/bin/ash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL

    CREATE TABLE IF NOT EXISTS public.hk_person
    (
        person_id serial NOT NULL,
        fullname text COLLATE pg_catalog."default",
        dob date NOT NULL,
        biological_sex text COLLATE pg_catalog."default",
        gender text COLLATE pg_catalog."default",
        blood_type text COLLATE pg_catalog."default",
        fitzpatrick_skin_type text COLLATE pg_catalog."default",
        CONSTRAINT hk_person_pkey PRIMARY KEY (person_id),
	      UNIQUE (fullname, dob)
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_person
        OWNER to $POSTGRES_USER;

    INSERT INTO public.hk_person(fullname, dob) VALUES ('default user', '1942-02-01');

    CREATE TABLE IF NOT EXISTS public.hk_quantity_record
    (
        record_id serial NOT NULL,
        person_id integer NOT NULL,
        hk_type text COLLATE pg_catalog."default" NOT NULL,
        hk_source text COLLATE pg_catalog."default" NOT NULL,
        source_version text COLLATE pg_catalog."default",
        device text COLLATE pg_catalog."default",
        creation_date timestamp with time zone,
        start_date timestamp with time zone NOT NULL,
        end_date timestamp with time zone NOT NULL,
        unit text COLLATE pg_catalog."default",
        hk_value double precision,
        CONSTRAINT hk_quantity_record_pkey PRIMARY KEY (record_id),
        CONSTRAINT hk_quantity_record_person_id_fkey FOREIGN KEY (person_id)
          REFERENCES public.hk_person (person_id) MATCH SIMPLE
          ON UPDATE NO ACTION
          ON DELETE NO ACTION,
        CONSTRAINT hk_quantity_record_unique UNIQUE (person_id, hk_type, hk_source, start_date, end_date)
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_quantity_record
        OWNER to $POSTGRES_USER;

    CREATE TABLE IF NOT EXISTS public.hk_category_record
    (
        record_id serial NOT NULL,
        person_id integer NOT NULL,
        hk_type text COLLATE pg_catalog."default" NOT NULL,
        hk_source text COLLATE pg_catalog."default" NOT NULL,
        source_version text COLLATE pg_catalog."default",
        device text COLLATE pg_catalog."default",
        creation_date timestamp with time zone,
        start_date timestamp with time zone NOT NULL,
        end_date timestamp with time zone NOT NULL,
        unit text COLLATE pg_catalog."default",
        hk_value text COLLATE pg_catalog."default",
        CONSTRAINT hk_category_record_pkey PRIMARY KEY (record_id),
        CONSTRAINT hk_category_record_person_id_fkey FOREIGN KEY (person_id)
          REFERENCES public.hk_person (person_id) MATCH SIMPLE
          ON UPDATE NO ACTION
          ON DELETE NO ACTION,
        CONSTRAINT hk_category_record_unique UNIQUE (person_id, hk_type, hk_source, start_date, end_date)
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_category_record
        OWNER to $POSTGRES_USER;

    CREATE TABLE IF NOT EXISTS public.hk_clinical_record
    (
        id text COLLATE pg_catalog."default" NOT NULL,
        subject text COLLATE pg_catalog."default" NOT NULL,
        effective_time timestamp with time zone NOT NULL,
        issued_time timestamp with time zone,
        hk_type text COLLATE pg_catalog."default",
        category text COLLATE pg_catalog."default",
        panel text COLLATE pg_catalog."default",
        CONSTRAINT hk_clinical_record_pkey PRIMARY KEY (id)
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_clinical_record
        OWNER to $POSTGRES_USER;

    CREATE TABLE IF NOT EXISTS public.hk_clinical_observation
    (
        record_id text COLLATE pg_catalog."default" NOT NULL,
        observation_id integer NOT NULL,
        observation_date timestamp with time zone NOT NULL,
        code_display text COLLATE pg_catalog."default",
        interpretation text COLLATE pg_catalog."default",
        ref_range_high double precision,
        ref_range_low double precision,
        unit text COLLATE pg_catalog."default",
        value double precision NOT NULL,
        CONSTRAINT hk_clinical_observation_pkey PRIMARY KEY (record_id, observation_id),
        CONSTRAINT hk_clinical_observation_record_id_fkey FOREIGN KEY (record_id)
            REFERENCES public.hk_clinical_record (id) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE NO ACTION
    )
    WITH (
        OIDS = FALSE
    )
    TABLESPACE pg_default;

    ALTER TABLE public.hk_clinical_observation
        OWNER to $POSTGRES_USER;
EOSQL
