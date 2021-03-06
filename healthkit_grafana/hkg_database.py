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

    def insert_activity_summaries(self, activity_summaries):
        upsert_sql = "INSERT INTO public.hk_activity_summary(" \
                     "  summary_date," \
                     "  active_energy_burned," \
                     "  active_energy_burned_goal," \
                     "  active_energy_burned_unit," \
                     "  apple_move_time," \
                     "  apple_move_time_goal, " \
                     "  apple_exercise_time, " \
                     "  apple_exercise_time_goal, " \
                     "  apple_stand_hours, " \
                     "  apple_stand_hours_goal" \
                     ") VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_activity_summary_pkey " \
                     "DO UPDATE " \
                     "SET (active_energy_burned, active_energy_burned_goal," \
                     "active_energy_burned_unit, apple_move_time, " \
                     "apple_move_time_goal, apple_exercise_time, " \
                     "apple_exercise_time_goal, apple_stand_hours, " \
                     "apple_stand_hours_goal) = " \
                     "(EXCLUDED.active_energy_burned, " \
                     "EXCLUDED.active_energy_burned_goal, " \
                     "EXCLUDED.active_energy_burned_unit, " \
                     "EXCLUDED.apple_move_time, " \
                     "EXCLUDED.apple_move_time_goal, " \
                     "EXCLUDED.apple_exercise_time, " \
                     "EXCLUDED.apple_exercise_time_goal, " \
                     "EXCLUDED.apple_stand_hours, " \
                     "EXCLUDED.apple_stand_hours_goal);"

        return self.insert_values(activity_summaries, upsert_sql)

    def insert_workout(self, workout) -> str:
        result = ''
        upsert_sql = "INSERT INTO public.hk_workout(" \
                     "workout_activity_type, " \
                     "duration, duration_unit, " \
                     "total_distance, total_distance_unit, " \
                     "total_energy_burned, total_energy_burned_unit, " \
                     "source_name, source_version, " \
                     "creation_date, start_date, end_date" \
                     ") VALUES (" \
                     "   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s" \
                     ")" \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_workout_unique " \
                     "DO UPDATE " \
                     "SET (duration, duration_unit," \
                     "total_distance, total_distance_unit, " \
                     "total_energy_burned, total_energy_burned_unit, " \
                     "source_version, creation_date) = " \
                     "(EXCLUDED.duration, " \
                     "EXCLUDED.duration_unit, " \
                     "EXCLUDED.total_distance, " \
                     "EXCLUDED.total_distance_unit, " \
                     "EXCLUDED.total_energy_burned, " \
                     "EXCLUDED.total_energy_burned_unit, " \
                     "EXCLUDED.source_version, " \
                     "EXCLUDED.creation_date) " \
                     "RETURNING workout_id;"

        cursor = self.connection.cursor()
        try:
            cursor.execute(upsert_sql, workout)
            result = cursor.fetchone()[0]
        except (Exception, psycopg2.Error) as error_ex:
            self.logger.error(
                "Error executing the following sql: %s" % upsert_sql)
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

    def insert_workout_metadata(self, workout_metadata):
        upsert_sql = "INSERT INTO public.hk_workout_metadata(" \
                     "  workout_id," \
                     "  meta_key," \
                     "  meta_value" \
                     ") VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_workout_metadata_pkey " \
                     "DO UPDATE " \
                     "SET meta_value = EXCLUDED.meta_value;"

        return self.insert_values(workout_metadata, upsert_sql)

    def insert_workout_events(self, workout_events):
        upsert_sql = "INSERT INTO public.hk_workout_event(" \
                     "  workout_id," \
                     "  event_type," \
                     "  event_date," \
                     "  duration," \
                     "  duration_unit" \
                     ") VALUES %s " \
                     "ON CONFLICT ON CONSTRAINT" \
                     "  hk_workout_event_unique " \
                     "DO NOTHING;"

        return self.insert_values(workout_events, upsert_sql)
