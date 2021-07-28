import datetime
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


def import_data():
    global DATABASE
    start = datetime.datetime.now()
    LOGGER.info("Starting Health Kit Exporter.")
    connect_to_db()
    xml_records = parse_file()
    split = datetime.datetime.now() - start
    LOGGER.info("Reading file took %s seconds." % split)

    quantity_records = get_quantity_records(xml_records)
    category_records = get_category_records(xml_records)

    LOGGER.info("Adding %s quantity records to the database." %
                len(quantity_records))
    DATABASE.insert_quantity_records(quantity_records)
    split = datetime.datetime.now() - split
    LOGGER.info("Inserting quantity records took %s seconds." % split)

    LOGGER.info("Adding %s category records to the database." %
                len(category_records))
    DATABASE.insert_category_records(category_records)
    split = datetime.datetime.now() - split
    LOGGER.info("Inserting category records took %s seconds." % split)

    end = datetime.datetime.now() - start

    LOGGER.info("Exiting, everything took %s seconds." % end)


if __name__ == "__main__":
    import_data()
