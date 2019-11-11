import datadog
import datetime

def initiatilize_datadog(**kwargs):
    datadog.initialize(**kwargs)


def query(tags=[], sources=None, start_time=None, end_time=None):
    batch_size = 30
    # datadog max is 32
    delta = end_time - start_time
    if delta <= datetime.timedelta(batch_size):
        print("Querying events for period: start={}; end={}".format(start_time, end_time))
        response = datadog.api.Event.query(
            start=datetime.datetime.timestamp(start_time),
            end=datetime.datetime.timestamp(end_time),
            sources=sources,
            tags=tags,
            unaggregated=True
        )
        if 'events' in response:
            events = response['events']
        else:
            raise Exception("Unexpected response: {}".format(response))
        for e in events:
            print(e)
        # DD creates some "aggregate events" for convenience. We are only interested in real events here.
        events = [e for e in events if e['is_aggregate'] == False]
        # Remove duplicates. DD sometimes returns same event twice
        events = list({e['id']:e for e in events}.values())
        print("({}) non-aggregate events returned in this batch".format(len(events)))
        return events
    else:
        last_30_days = query(
            tags=tags,
            start_time=(end_time - datetime.timedelta(batch_size)),
            end_time=end_time
        )
        # query rest
        rest = query(
            tags=tags,
            start_time=start_time,
            end_time=(end_time - datetime.timedelta(batch_size))
        )
        return [*rest, *last_30_days]


def query_jenkins_job_events(job_name, start_time=None, end_time=None):
    return query(
        tags=[
            "job:{}".format(job_name),
            'result:success'
        ],
        sources='jenkins',
        start_time=start_time,
        end_time=end_time
    )
