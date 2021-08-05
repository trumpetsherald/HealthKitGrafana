import datetime
import json
import os
import sys
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
        records = xml_doc.getElementsByTagName('Record')
        workouts = xml_doc.getElementsByTagName('Workout')
        activity_summaries = xml_doc.getElementsByTagName('ActivitySummary')
        clinical_records = xml_doc.getElementsByTagName('ClinicalRecord')

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
                LOGGER.warn("Found duplicate records: %s" % duplicates[key])

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
                LOGGER.warn("Found duplicate records: %s" % duplicates[key])

    return result


def get_observations_from_report(report):
    result = []
    record_id = report['id']

    for observation in report['contained']:
        if 'valueString' in observation:
            continue

        if 'valueQuantity' not in observation:
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
def get_record_and_observations(report):
    try:
        report_id = report['id']
        subject = report['subject']['reference']
        effective_time = report['effectiveDateTime']
    except KeyError as ke:
        LOGGER.error("Couldn't get required fields for report.")

    issue_time = report.get('issued', None)
    hk_type = report.get('resourceType')
    category = report.get('category', {}).get('coding', [])[0].get('code)')
    panel = report.get('code', {}).get('text')
    observations = get_observations_from_report(report)

    return (report_id, subject, effective_time,
            issue_time, hk_type, category, panel), observations


def get_clinical_records_and_observations():
    records = []
    record_ids = []
    dup_record_count = 0
    dup_records = {}
    all_observations = []
    clinical_path = EXPORT_DIR_PATH + "/clinical-records/"

    if os.path.isdir(clinical_path):
        for clinical_file in os.listdir(clinical_path):
            file_path = clinical_path + clinical_file
            # todo gag a maggot fix this
            if os.path.isfile(file_path) and clinical_file.startswith(
                    "DiagnosticReport"):
                with open(file_path) as report_file:
                    report = json.load(report_file)
                    record, observations = get_record_and_observations(report)
                    if record and observations:
                        # Ugly hack to handle identical fhir json files
                        # that have different filenames
                        if record[0] not in record_ids:
                            record_ids.append(record[0])
                            records.append(record)
                            all_observations.extend(observations)
                        else:
                            if record[0] not in dup_records:
                                dup_records[record[0]] = []
                            dup_records[record[0]].append(clinical_file)
                            dup_record_count += 1
                    else:
                        LOGGER.error("Report or observations were null.")

    for dupe, files in dup_records.items():
        print('ID is duplicated in the following files:')
        for file in files:
            print("\t" + file)

    return records, all_observations


def import_me(me_xml):
    pass


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
    pass


def import_activity_summaries(summaries_xml):
    pass


def import_clinical_records():
    global DATABASE
    start = datetime.datetime.now()
    records, observations = get_clinical_records_and_observations()

    DATABASE.insert_clinical_records(records)
    DATABASE.insert_clinical_observations(observations)
    end = datetime.datetime.now() - start
    LOGGER.info("Adding Clinical Records (labs) took %s second." % end)


def import_data():
    global DATABASE
    start = datetime.datetime.now()
    LOGGER.info("Starting Health Kit Exporter.")

    connect_to_db()
    me, records, workouts, activity_summaries, \
        clinical_records = parse_export_xml()

    import_me(me)
    import_records(records)
    import_clinical_records()

    end = datetime.datetime.now()
    LOGGER.info("Exiting, everything took %s seconds." % (end - start))


if __name__ == "__main__":
    import_data()
