import datetime
import json
import os
import pathlib
from healthkit_grafana import hkg_logger
from healthkit_grafana import hkg_database
from xml.dom import minidom

LOGGER: hkg_logger = hkg_logger.LOGGER
DATABASE: hkg_database
EXPORT_DIR_PATH = os.environ.get(
    'HKG_EXPORT_FILE_PATH',
    '/opt/healthkit_grafana/apple_health_export')

DEFAULT_PERSON_ID = 1
STRIP_PREFIXES = [
    'HKQuantityTypeIdentifier',
    'HKCategoryTypeIdentifier'
]

LAB_TYPE_DIAGNOSTIC_REPORT = 'DiagnosticReport'
LAB_SOURCE_LABCORP = 'labcorp'

HKCategoryValueSleepAnalysisInBed = "HKCategoryValueSleepAnalysisInBed"
HKCategoryValueSleepAnalysisAsleep = "HKCategoryValueSleepAnalysisAsleep"
HKCategoryValueSleepAnalysisAwake = "HKCategoryValueSleepAnalysisAwake"
HKCategoryValueAppleStandHourIdle = "HKCategoryValueAppleStandHourIdle"
HKCategoryValueAppleStandHourStood = "HKCategoryValueAppleStandHourStood"
HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit = \
    "HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit"


def connect_to_db():
    global DATABASE
    LOGGER.info("Connecting to Database.")

    db_host, db_name, db_username, db_password = None, None, None, None

    try:
        db_host = os.environ['HKG_DB_HOST']
        db_name = os.environ['HKG_DB_NAME']
        db_username = os.environ['HKG_DB_USERNAME']
        db_password = os.environ['HKG_DB_PASSWORD']
    except KeyError as ke:
        print("Key not found %s", ke)
        exit(42)

    DATABASE = hkg_database.HKGDatabase(db_host, db_name, db_username,
                                        db_password)
    # noinspection PyBroadException
    try:
        DATABASE.connect_to_db()
    except Exception:
        LOGGER.error("Could not connect to database after 10 retries.")
        exit(42)


def parse_export_xml() -> []:
    me = None
    records = None
    workouts = None
    activity_summaries = None
    clinical_records = None
    LOGGER.info("Parsing export file.")
    file_path = EXPORT_DIR_PATH + "/export.xml"

    if os.path.isfile(file_path):
        xml_doc = minidom.parse(file_path)
        me = xml_doc.getElementsByTagName('Me')
        if me:
            LOGGER.info("Me element found.")

        records = xml_doc.getElementsByTagName('Record')
        if records:
            LOGGER.info("%s records found." % len(records))

        workouts = xml_doc.getElementsByTagName('Workout')
        if workouts:
            LOGGER.info("%s workouts found." % len(workouts))

        activity_summaries = xml_doc.getElementsByTagName('ActivitySummary')
        if activity_summaries:
            LOGGER.info(
                "%s activity_summaries found." % len(activity_summaries))

        clinical_records = xml_doc.getElementsByTagName('ClinicalRecord')
        if records:
            LOGGER.info("%s clinical_records found." % len(clinical_records))

    return me, records, workouts, activity_summaries, clinical_records


def get_quantity_records(xml_records):
    result = []
    duplicates = {}

    for record in xml_records:
        record_type = record.getAttribute('type')

        if record_type.startswith("HKQuantityTypeIdentifier"):
            value = record.getAttribute('value')
            if not value:
                value = 0.0

            key = str(DEFAULT_PERSON_ID) + record_type + \
                record.getAttribute('sourceName') + \
                record.getAttribute('startDate') + \
                record.getAttribute('endDate')

            quantity_record = (
                DEFAULT_PERSON_ID,
                record_type,
                record.getAttribute('sourceName'),
                record.getAttribute('sourceVersion'),
                record.getAttribute('device'),
                record.getAttribute('creationDate'),
                record.getAttribute('startDate'),
                record.getAttribute('endDate'),
                record.getAttribute('unit'),
                value
            )
            if key not in duplicates:
                duplicates[key] = []

            duplicates[key].append(quantity_record)

            if len(duplicates[key]) == 1:
                result.append(quantity_record)
            else:
                LOGGER.warning("Found duplicate records: %s" % duplicates[key])

    return result


def get_category_records(xml_records):
    result = []
    duplicates = {}

    for record in xml_records:
        record_type = record.getAttribute('type')

        if record_type.startswith("HKCategoryTypeIdentifier"):
            value = record.getAttribute('value')
            if not value:
                value = "Not Set"

            # This is ugly but...
            # My data has records where type, source, start, and end
            # dates are all the same and the create date is seconds off
            # Since I can only depend on those 4 items being present
            # those are the unique constraints on the db. The other option
            # (and this may be valid) is to do nothing on conflict vs update
            # the other fields.
            key = str(DEFAULT_PERSON_ID) + record_type + \
                record.getAttribute('sourceName') + \
                record.getAttribute('startDate') + \
                record.getAttribute('endDate')

            category_record = (
                DEFAULT_PERSON_ID,
                record_type,
                record.getAttribute('sourceName'),
                record.getAttribute('sourceVersion'),
                record.getAttribute('device'),
                record.getAttribute('creationDate'),
                record.getAttribute('startDate'),
                record.getAttribute('endDate'),
                record.getAttribute('unit'),
                value
            )
            if key not in duplicates:
                duplicates[key] = []

            duplicates[key].append(category_record)

            if len(duplicates[key]) == 1:
                result.append(category_record)
            else:
                LOGGER.debug("Found duplicate records: %s" % duplicates[key])

    LOGGER.info("Found %s records and %s duplicates." % (
        len(result), len(duplicates))
    )

    return result


def get_observations_from_report(report):
    result = []
    record_id = report['id']

    for observation in report['contained']:
        if 'valueString' in observation:
            LOGGER.debug(
                "Observation value is a string, skipping: %s" % observation)
            continue

        if 'valueQuantity' not in observation:
            LOGGER.warning(
                "Observation is missing a quantity, skipping: %s" % observation
            )
            continue

        observation_id = observation['id']
        observation_date = observation['effectiveDateTime']
        code_display = None
        coding_list = observation.get('code', []).get('coding')

        if coding_list:
            code_display = coding_list[0].get('display')

        interpretation = None
        coding_list = observation.get('interpretation', []).get('coding')

        if coding_list:
            interpretation = coding_list[0].get('code')

        reference_range = observation.get('referenceRange', None)
        reference_high, reference_low = None, None

        if reference_range:
            reference_high = reference_range[0].get('high', {}).get('value')
            reference_low = reference_range[0].get('low', {}).get('value')

        unit = observation['valueQuantity'].get('unit')
        value = observation['valueQuantity']['value']

        result.append(
            (record_id, observation_id, observation_date, code_display,
             interpretation, reference_high, reference_low, unit, value)
        )

    return result


#  This will return a clinical record tuple and a list of observation tuples
def get_record_and_observations(report, hk_type, source_name, resource_path):
    try:
        report_id = report['id']
        subject = report['subject']['reference']
        effective_time = report['effectiveDateTime']
    except KeyError as ke:
        LOGGER.error("Couldn't get required fields for report.", ke)
        return None, None

    issue_time = report.get('issued', None)
    category = report.get('category', {}).get('coding', [])[0].get('code')
    panel = report.get('code', {}).get('text')
    observations = get_observations_from_report(report)

    return (report_id, subject, effective_time, issue_time, hk_type,
            source_name, resource_path, category, panel), observations


def get_clinical_records_and_observations(clinical_records_xml):
    records = []
    all_observations = []

    for cr in clinical_records_xml:
        record_id = cr.getAttribute('identifier')
        hk_type = cr.getAttribute('type')
        source_name = cr.getAttribute('sourceName')
        resource_path = cr.getAttribute('resourceFilePath')

        if not all([record_id, hk_type, source_name, resource_path]):
            LOGGER.error("Required field missing, skipping record %s" % cr)
            continue

        if hk_type != LAB_TYPE_DIAGNOSTIC_REPORT:
            LOGGER.warning("Currently only Diagnostic Reports are supported. "
                           "Skipping record: %s" % cr)
            continue

        if source_name != LAB_SOURCE_LABCORP:
            LOGGER.warn("I haven't tested against anything but "
                        "LabCorp so currently I'm playing it "
                        "safe and skipping record: %s" % cr)

        file_path = EXPORT_DIR_PATH + resource_path
        if not os.path.isfile(file_path):
            LOGGER.error("Skipping clinical record: %s.\n"
                         "I couldn't find the file resource at the "
                         "indicated path %s. Please ensure this path "
                         "is correct." % (cr, file_path))
            continue

        with open(file_path) as report_file:
            report = json.load(report_file)
            record, observations = get_record_and_observations(
                report, hk_type, source_name, resource_path)
            if record and observations:
                records.append(record)
                all_observations.extend(observations)
            else:
                LOGGER.error("Report or observations were null.")

    return records, all_observations


def import_me(me_xml):
    LOGGER.debug(me_xml)


def import_records(records_xml):
    start = datetime.datetime.now()
    LOGGER.info("Importing export.xml")
    quantity_records = get_quantity_records(records_xml)
    category_records = get_category_records(records_xml)
    read_done = datetime.datetime.now()
    LOGGER.info("Reading export.xml took %s seconds." % (read_done - start))

    LOGGER.info("Adding %s quantity records to the database." %
                len(quantity_records))
    DATABASE.insert_quantity_records(quantity_records)

    LOGGER.info("Adding %s category records to the database." %
                len(category_records))
    DATABASE.insert_category_records(category_records)

    insert_done = datetime.datetime.now()
    LOGGER.info("Inserting category records took %s seconds." %
                (insert_done - read_done))
    LOGGER.info("Total time to parse export.xml and update DB was %s" %
                (insert_done - start))


def import_workouts(workouts_xml):
    LOGGER.debug(workouts_xml)


def import_activity_summaries(summaries_xml):
    global DATABASE
    start = datetime.datetime.now()
    summaries = []

    for summary in summaries_xml:
        summary_date = summary.getAttribute('dateComponents')

        if not summary_date:
            LOGGER.error("Date was null for summary: %s" % summary)
            continue

        active_energy_burned = summary.getAttribute('activeEnergyBurned')
        active_energy_burned_goal = summary.getAttribute(
            'activeEnergyBurnedGoal')
        active_energy_burned_unit = summary.getAttribute(
            'activeEnergyBurnedUnit')
        apple_move_time = summary.getAttribute('appleMoveTime')
        apple_move_time_goal = summary.getAttribute('appleMoveTimeGoal')
        apple_exercise_time = summary.getAttribute('appleExerciseTime')
        apple_exercise_time_goal = summary.getAttribute(
            'appleExerciseTimeGoal')
        apple_stand_hours = summary.getAttribute('appleStandHours')
        apple_stand_hours_goal = summary.getAttribute('appleStandHoursGoal')

        summaries.append(
            (summary_date, active_energy_burned, active_energy_burned_goal,
             active_energy_burned_unit, apple_move_time, apple_move_time_goal,
             apple_exercise_time, apple_exercise_time_goal,
             apple_stand_hours, apple_stand_hours_goal)
        )

    DATABASE.insert_activity_summaries(summaries)

    end = datetime.datetime.now() - start
    LOGGER.info("Adding Activity Summaries took %s seconds." % end)


def remove_duplicate_clinical_records(clinical_records_xml):
    id_record_map = {}
    duplicates = []
    skipped = 0
    files_not_found = 0

    for cr in clinical_records_xml:
        # This should never be null
        identifier = cr.getAttribute('identifier')

        if identifier not in id_record_map:
            id_record_map[identifier] = cr
        else:
            duplicates.append(cr)

    clinical_path = EXPORT_DIR_PATH + "/clinical-records/"

    if os.path.isdir(clinical_path):
        duplicate_path = os.path.join(clinical_path, 'duplicates')

        pathlib.Path(duplicate_path).mkdir(exist_ok=True)

        for dup in duplicates:
            file_path = dup.getAttribute('resourceFilePath')

            current_path = os.path.join(
                clinical_path, os.path.basename(file_path))
            new_path = os.path.join(
                duplicate_path, os.path.basename(file_path))

            if not os.path.isfile(current_path):
                skipped += 1
                if os.path.isfile(new_path):
                    LOGGER.debug(
                        "%s was already moved into duplicates." % new_path)
                else:
                    LOGGER.error("No file found at %s to move to "
                                 "duplicates." % current_path)
                    files_not_found += 1
                continue

            os.rename(current_path, new_path)

    LOGGER.info("Duplicate Clinical Records Detected: %s" % len(duplicates))
    LOGGER.info("Duplicate Clinical Records Moved: %s" % (
            len(duplicates) - skipped))
    LOGGER.info("Duplicate Clinical Records Skipped: %s" % skipped)
    LOGGER.info("Clinical Records Missing Files: %s" % files_not_found)

    return id_record_map.values()


def import_clinical_records(clinical_records_xml):
    global DATABASE
    start = datetime.datetime.now()

    records, observations = \
        get_clinical_records_and_observations(clinical_records_xml)

    DATABASE.insert_clinical_records(records)
    DATABASE.insert_clinical_observations(observations)
    end = datetime.datetime.now() - start
    LOGGER.info("Adding Clinical Records (labs) took %s seconds." % end)


def import_data():
    global DATABASE
    start = datetime.datetime.now()
    LOGGER.info("Starting Health Kit Exporter.")

    connect_to_db()
    me, records, workouts, activity_summaries, \
        clinical_records = parse_export_xml()

    import_me(me)
    import_records(records)
    import_workouts(workouts)
    import_activity_summaries(activity_summaries)
    unique_records = remove_duplicate_clinical_records(clinical_records)
    import_clinical_records(unique_records)

    end = datetime.datetime.now()
    LOGGER.info("Exiting, everything took %s seconds." % (end - start))


if __name__ == "__main__":
    import_data()
