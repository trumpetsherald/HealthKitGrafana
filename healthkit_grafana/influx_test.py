from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

client = InfluxDBClient(url="http://localhost:8086",
                        token="3d95d28c-5282-4e18-b173-2329a8a74a0f",
                        org="HealthKitGrafana")

write_api = client.write_api(write_options=SYNCHRONOUS)
reesults = write_api.write("health_bucket", "HealthKitGrafana",
                [
                    {
                        "time": "2021-10-29T10:00:00Z",
                        "measurement": "h2o_feet",
                        "tags": {
                            "location": "sand_creek"
                        },
                        "fields": {
                            "water_level": 2
                        }
                    }
                ])

print(results)

