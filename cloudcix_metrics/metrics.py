# python
import atexit
import logging
import subprocess
import urllib3
from collections import namedtuple
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool
from typing import List, Dict, Callable, Optional, Any

# libs
import influxdb
from cloudcix.conf import settings

# Suppress InsecureRequestWarnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Pool = ThreadPool(1)


def stop_pool():
    Pool.close()
    Pool.join()


atexit.register(stop_pool)

INFLUX_CLIENT = None

# Define a helper data type for Influx data
InfluxData = Dict[str, Any]

Metric = namedtuple('Metric', ['table', 'value', 'tags'])


def _generate_data_packet(measurement: str, fields: dict, tags: dict={}) -> List[InfluxData]:
    """
    Generates a data packet for the current region with the given measure name
    and whatever fields are passed to this method, and turns it into a format to be sent to influx
    :param measurement: The name of the measurement to send
    :param fields: Key-value pairs of data to be sent. Not indexed in Influx
    :param tags: Extra meta-data to be associated with a data point. Indexed in Influx
    :return: A prepared data packet in a form ready to be sent to InfluxDB
    """
    extra_tags = getattr(settings, 'CLOUDCIX_INFLUX_TAGS', {})
    tags.update(extra_tags)
    data = [{
        'measurement': measurement,
        'tags': tags,
        'fields': fields,
        'time': datetime.utcnow(),
    }]
    return data


def _get_current_git_sha() -> str:
    """
    Finds the current git commit sha and returns it
    :return: The sha of the current commit
    """
    return subprocess.check_output([
        'git',
        'describe',
        '--always',
    ]).strip().decode()


def _get_influx_client() -> Optional[influxdb.InfluxDBClient]:
    """
    Lazy creates a client for connecting to our InfluxDB instance
    :return: An InfluxDBClient that can log metrics to our instance of Influx
    """
    global INFLUX_CLIENT
    if INFLUX_CLIENT is None and settings.CLOUDCIX_INFLUX_DATABASE is not None:
        try:
            INFLUX_CLIENT = influxdb.InfluxDBClient(
                host=settings.CLOUDCIX_INFLUX_URL,
                port=settings.CLOUDCIX_INFLUX_PORT,
                database=settings.CLOUDCIX_INFLUX_DATABASE,
                ssl=settings.CLOUDCIX_INFLUX_PORT == 443,
            )
            # Ensure the database exists
            INFLUX_CLIENT.create_database(settings.CLOUDCIX_INFLUX_DATABASE)
        except Exception:
            logging.getLogger('cloudcix_metrics._get_influx_client').error(
                'Error connecting to Influx.',
                exc_info=True,
            )
    return INFLUX_CLIENT


def current_commit(commit=None):
    commit = commit or _get_current_git_sha()
    _post_metrics('commit', commit)


def prepare_metrics(preprocess: Callable[[Optional[Dict]], Metric], **kwargs):
    """
    Places the function preprocess in the thread pool queue. Currently assumes that tags are determined in preprocess.
    :param preprocess: a function that takes in kwargs and returns a named tuple with the fields table, value and tags.
    table is a str, value is any (probably primitives only) and tags is a dict
    """
    Pool.apply_async(_post, args=(preprocess,), kwds=kwargs)


def _post(preprocess, **kwargs):
    metric = preprocess(**kwargs)
    if metric is None:
        return
    _post_metrics(metric.table, metric.value, metric.tags)


def _post_metrics(measurement: str, value, tags: dict={}):
    """
    Sends the given k-v pair (measurement->value) to influx
    along with the given tags
    :param measurement: the key for the significant metric field
    :param value: the value for the significant metric field
    :param tags: the relevant tags
    """
    client = _get_influx_client()
    if client is None:
        return
    client.write_points(
        _generate_data_packet(
            measurement,
            {'value': value},
            tags,
        ),
    )
