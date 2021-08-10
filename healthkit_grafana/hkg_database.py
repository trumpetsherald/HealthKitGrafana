import psycopg2
import psycopg2.extras as extras
from retry import retry
from healthkit_grafana import hkg_logger


class HKGDatabaseException(Exception):
    pass


class HKGDatabase(object):
    def __init__(self, host, name, user, password):
        self.logger = hkg_logger.LOGGER
        self.host = host
        self.name = name
        self.username = user
        self.password = password
        self.connection = None

    #  Wait up to 17 mins attempting to reconnect
    @retry((Exception, psycopg2.DatabaseError), tries=10, delay=1, backoff=2)
    def connect_to_db(self):
        result = True
        conn_params = {
            "host": self.host,
            "database": self.name,
            "user": self.username,
            "password": self.password
        }

        if not self.connection:
            try:
                self.connection = psycopg2.connect(**conn_params)

                # create a cursor
                cur = self.connection.cursor()

                # execute a statement
                self.logger.debug('PostgreSQL database version:')
                cur.execute('SELECT version()')

                # display the PostgreSQL database server version
                db_version = cur.fetchone()
                self.logger.debug(db_version)

                # close communication with the PostgreSQL DB
                cur.close()
            except (Exception, psycopg2.DatabaseError) as error:
                self.logger.error("Error connecting to database:")
                self.logger.error(error)
                raise error

        return result

    def close(self):
        self.connection.close()

    def insert_values(self, records, sql):
        result = True
        cursor = self.connection.cursor()
        try:
            extras.execute_values(cursor, sql, records)
        except (Exception, psycopg2.Error) as error_ex:
            self.logger.error("Error executing the following sql: %s" % sql)
            self.logger.error("Error: " + str(error_ex))
            result = False
        else:
            try:
                self.connection.commit()
            except (Exception, psycopg2.Error) as error_ex:
                self.logger.error("Error on commit.")
                self.logger.error("Error: " + str(error_ex))
                self.connection.rollback()
                result = False
        finally:
            cursor.close()

        return result

    def get_values(self, sql, data=None):
        cursor = self.connection.cursor()
        try:
            if data:
                cursor.execute(sql, data)
            else:
                cursor.execute(sql)
            result = cursor.fetchall()
        except (Exception, psycopg2.Error) as error_ex:
            self.logger.error("Error executing the following sql: %s" % sql)
            self.logger.error("Error: " + str(error_ex))
            result = False
        finally:
            cursor.close()

        return result

    def get_health_records(self):
        result = self.get_values('SELECT * FROM public.hk_record')

        if result is False:
            self.logger.error(
                "An error occurred while getting all health records.")
        else:
            self.logger.debug(
                "Returning %s health records from DB query." % len(result))

        return result

    def reset_db(self):
        result = True
        reset_records_sql = \
            "DELETE FROM public.hk_record;" \
            "ALTER SEQUENCE hk_record_record_id_seq RESTART WITH 1;"

        cursor = self.connection.cursor()
        try:
            cursor.execute(reset_records_sql)
        except (Exception, psycopg2.Error) as error_ex:
            self.logger.error("Error executing the following sql: %s"
                              % reset_records_sql)
            self.logger.error("Error: " + str(error_ex))
            result = False
        finally:
            cursor.close()

        return result

    def get_health_record(self, record_id):
        result = self.get_values(
            'SELECT * FROM public.hk_record where record_id = %s',
            (record_id,))

        if result is False:
            self.logger.error(
                "An error occurred while getting the health record.")
        else:
            self.logger.debug(
                "Got record_id: %s from DB." % record_id)

        return result[0]

    def insert_quantity_records(self, health_records):
        upsert_sql = "INSERT INTO public.hk_quantity_record(" \
                     "person_id, " \
                     "hk_type, " \
                     "hk_source, " \
                     "source_version, " \
                     "device, " \
                     "creation_date, " \
                     "start_date, " \
                     "end_date, " \
                     "unit, " \
                     "hk_value) " \
                     "VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_quantity_record_unique " \
                     "DO UPDATE " \
                     "SET (source_version, device, " \
                     "creation_date, unit, hk_value) = " \
                     "(EXCLUDED.source_version, " \
                     "EXCLUDED.device, EXCLUDED.creation_date, " \
                     "EXCLUDED.unit, EXCLUDED.hk_value);"

        return self.insert_values(health_records, upsert_sql)

    def insert_category_records(self, health_records):
        upsert_sql = "INSERT INTO public.hk_category_record(" \
                     "person_id, " \
                     "hk_type, " \
                     "hk_source, " \
                     "source_version, " \
                     "device, " \
                     "creation_date, " \
                     "start_date, " \
                     "end_date, " \
                     "unit, " \
                     "hk_value) " \
                     "VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_category_record_unique " \
                     "DO UPDATE " \
                     "SET (source_version, device, " \
                     "creation_date, unit, hk_value) = " \
                     "(EXCLUDED.source_version, " \
                     "EXCLUDED.device, EXCLUDED.creation_date, " \
                     "EXCLUDED.unit, EXCLUDED.hk_value);"

        return self.insert_values(health_records, upsert_sql)

    def insert_clinical_records(self, clinical_records):
        upsert_sql = "INSERT INTO public.hk_clinical_record(" \
                     "  id," \
                     "  subject," \
                     "  effective_time," \
                     "  issued_time," \
                     "  hk_type," \
                     "  source_name," \
                     "  resource_path," \
                     "  category, " \
                     "  panel" \
                     ") VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_clinical_record_pkey " \
                     "DO UPDATE " \
                     "SET (subject, effective_time," \
                     "issued_time, hk_type, source_name, " \
                     "resource_path, category, panel) = " \
                     "(EXCLUDED.subject, EXCLUDED.effective_time, " \
                     "EXCLUDED.issued_time, EXCLUDED.hk_type, " \
                     "EXCLUDED.source_name, EXCLUDED.resource_path, " \
                     "EXCLUDED.category, EXCLUDED.panel);"

        return self.insert_values(clinical_records, upsert_sql)

    def insert_clinical_observations(self, clinical_observations):
        upsert_sql = "INSERT INTO public.hk_clinical_observation(" \
                     "  record_id," \
                     "  observation_id," \
                     "  observation_date," \
                     "  code_display," \
                     "  interpretation," \
                     "  ref_range_high, " \
                     "  ref_range_low, " \
                     "  unit, " \
                     "  value" \
                     ") VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_clinical_observation_pkey " \
                     "DO UPDATE " \
                     "SET (observation_date, code_display," \
                     "interpretation, ref_range_high, ref_range_low, " \
                     "unit, value) = " \
                     "(EXCLUDED.observation_date, EXCLUDED.code_display, " \
                     "EXCLUDED.interpretation, EXCLUDED.ref_range_high, " \
                     "EXCLUDED.ref_range_low, EXCLUDED.unit, " \
                     "EXCLUDED.value);"

        return self.insert_values(clinical_observations, upsert_sql)