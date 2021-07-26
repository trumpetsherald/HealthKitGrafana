import os
import sys
from healthkit_grafana import hkg_logger
from healthkit_grafana import hkg_database
from xml.dom import minidom

LOGGER: hkg_logger = hkg_logger.LOGGER
DATABASE: hkg_database
EXPORT_FILE_PATH = os.environ.get(
            'HKG_EXPORT_FILE_PATH',
            '/opt/healthkit_grafana/apple_health_export/export.xml')

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
    global DATABASE, EXPORT_FILE_PATH
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


def parse_file() -> []:
    LOGGER.info("Parsing export file.")
    xml_doc = minidom.parse(EXPORT_FILE_PATH)
    record_list = xml_doc.getElementsByTagName('Record')

    return record_list


def import_data():
    global DATABASE
    LOGGER.info("Starting Health Kit Exporter.")
    connect_to_db()
    record_list = parse_file()
    record_tuples = []

    DATABASE.reset_db()

    for record in record_list:
        value = record.getAttribute('value')
        if not value:
            value = 0.0

        if value == HKCategoryValueSleepAnalysisInBed:
            value = 0
        elif value == HKCategoryValueSleepAnalysisAsleep:
            value = 1
        elif value == HKCategoryValueSleepAnalysisAwake:
            value = 2
        elif value == HKCategoryValueAppleStandHourIdle:
            value = 0
        elif value == HKCategoryValueAppleStandHourStood:
            value = 1
        elif value == HKCategoryValueHeadphoneAudioExposureEventSevenDayLimit:
            value = 1

        record_tuples.append(
            (
                record.getAttribute('type'),
                record.getAttribute('sourceName'),
                record.getAttribute('sourceVersion'),
                record.getAttribute('device'),
                record.getAttribute('creationDate'),
                record.getAttribute('startDate'),
                record.getAttribute('endDate'),
                record.getAttribute('unit'),
                value
            )
        )

    LOGGER.info("Updating the database.")
    DATABASE.insert_health_records(record_tuples)


if __name__ == "__main__":
    print(sys.path)
    import_data()
