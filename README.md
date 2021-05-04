# CloudCIX Metrics

Provides the function needed for preparing and sending metrics to InfluxDB

## **NOTE**

Your `settings.py` must contain a line such as `CLOUDCIX_INFLUX_DATABASE = 'stage_membership'` to define which InfluxDB Database the metrics get posted to

## Installation

Add the following to your `requirements.txt`

`git+https://gitlab.cloudcix.com/CloudCIX/cloudcix_metrics`

## Usage

3 settings are needed in `settings.py`:

- CLOUDCIX_INFLUX_URL
  - the url of the InfluxDB server

- CLOUDCIX_INFLUX_PORT
  - the port on which InfluxDB is listening, generally 80 because reverse proxied

- CLOUDCIX_INFLUX_DATABASE
  - the name of the database in InfluxDB e.g. for the APIs it is `cloudcix_metrics`

- CLOUDCIX_INFLUX_TAGS
  -  optional settings for adding static tags to all points

Import the two functions:

`from cloudcix_metrics import prepare_metrics, Metric`

`prepare_metrics` must be given a function which takes in kwargs and returns a `Metric` object with the respective parameters `table`, `value` and `tags`, which are of type string, any and dict respectively. This queues the supplied function in the thread pool. The function can then process the kwargs and returns the data to be sent to InfluxDB.

## Example

```py
# settings.py
CLOUDCIX_INFLUX_URL = 'influx.cloudcix.com'
CLOUDCIX_INFLUX_PORT = 80
CLOUDCIX_INFLUX_DATABSE = 'cloudcix_metrics'
CLOUDCIX_INFLUX_TAGS = {
    'service_name': 'stage_membership',
}


# somefile.py
from cloudcix_metrics import prepare_metrics, Metric

class MemberCollection(APIView):
    def post(self, request: HttpRequest) -> Response:

        # ...

        controller = MemberCreateController(
            data=request.data,
            request=request,
        )

        # ...

        # self._on_member_create is queued and given the member primary as a kwarg
        prepare_metrics(self._on_member_create, pk=controller.instance.pk)

        return Response(status=status.HTTP_201_CREATED)

    def _on_member_create(self, pk):
        # the metric to be posted is returned with the table name 'member_create' and the value of pk with no tags.
        # any necesssary preprocessing can be done here eg. getting request IP
        return Metric('member_create', pk, {})
```