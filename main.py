import time
import datetime
import logging
import re
import sqlalchemy
import sqlalchemy.dialects.postgresql
import datadog
import ah_config
import ah_db


deployments_table_name = 'deployments'
DEPLOYMENTS_TABLE = sqlalchemy.Table(
    deployments_table_name,
    sqlalchemy.MetaData(),
    sqlalchemy.Column('artifact', sqlalchemy.TEXT),
    sqlalchemy.Column('deployed_at', sqlalchemy.TIMESTAMP(timezone=True)),
    sqlalchemy.Column('ingested_at', sqlalchemy.TIMESTAMP(timezone=True)),
    sqlalchemy.Column('is_rollback', sqlalchemy.BOOLEAN),
    sqlalchemy.Column('datadog_event_id', sqlalchemy.TEXT),
    sqlalchemy.Column('jenkins_job_name', sqlalchemy.TEXT),
    sqlalchemy.Column('jenkins_build_num', sqlalchemy.INTEGER),
    sqlalchemy.Column('jenkins_event_title', sqlalchemy.TEXT),
)

def parse_jenkins_deploy_job_event(event):
    print(event)
    return {
        "deployed_at": datetime.datetime.fromtimestamp(event['date_happened'], datetime.timezone.utc),
        "is_rollback": False,
        "jenkins_event_title": event['title'],
        "datadog_event_id": event['id'],
        "jenkins_build_num": re.search('build #(\d+) ', event['title']).group(1),
    }

def upsert_deploys(conn, deploys):
    stmt = sqlalchemy.dialects.postgresql.insert(DEPLOYMENTS_TABLE)
    # TODO match on datadog event id instead?
    stmt = stmt.on_conflict_do_nothing(index_elements=['artifact', 'deployed_at'])
    print("Upserting ({}) deployments".format(len(deploys)))
    [print(d) for d in deploys]
    res = conn.execute(stmt, deploys)


# or tags? which level of abstraction
def query_jenkins_job_events(job_name, start_time=None, end_time=None):
    batch_size = 30
    # datadog max is 32
    delta = end_time - start_time
    if delta <= datetime.timedelta(batch_size):
        print("Querying events for period: start={}; end={}".format(start_time, end_time))
        response = datadog.api.Event.query(
            start=datetime.datetime.timestamp(start_time),
            end=datetime.datetime.timestamp(end_time),
            sources='jenkins',
            tags=[
                "job:{}".format(job_name),
                'result:success'
            ],
            unaggregated=True
        )
        # TODO handle bad response
        events = response['events']
        for e in events:
            print(e)
        print(events)
        print("({}) events returned in this batch".format(len(events)))
        return events
    else:
        last_30_days = query_jenkins_job_events(
            job_name,
            start_time=(end_time - datetime.timedelta(batch_size)),
            end_time=end_time
        )
        # query rest
        rest = query_jenkins_job_events(
            job_name,
            start_time=start_time,
            end_time=(end_time - datetime.timedelta(batch_size))
        )
        return [*rest, *last_30_days]


events = []
def ingest_nativeapi_deploys(conn, start_time, end_time):
    napi_job_name = 'nativeapi/prod.jobs/bld-stage-deploy'
    artifact_name = 'nativeapi'
    ingest_time   = datetime.datetime.now()

    events = query_jenkins_job_events(napi_job_name,
                                      start_time=start_time,
                                      end_time=end_time)
    # print(events)
    print("Received ({}) events".format(len(events)))
    if len(events) == 1:
        print("Exiting")
        return
    # DD creates some "aggregate events" for convenience. We are only interested in real events here.
    deploys = [parse_jenkins_deploy_job_event(event) for event in events if event['is_aggregate'] == False]
    # Remove duplicates. DD sometimes returns same event twice
    deploys = list({d['datadog_event_id']:d for d in deploys}.values())
    for deploy in deploys:
        deploy.update({
            "artifact": artifact_name,
            "jenkins_job_name": napi_job_name,
            "ingested_at": ingest_time
        })
    # TODO error or warn or log on col mismatch
    upsert_deploys(conn, deploys)


if __name__ == "__main__":
    ah_config.initialize()

    datadog.initialize(api_key=ah_config.get("datadog_credentials.api_key"),
                       app_key=ah_config.get("datadog_credentials.app_key"))

    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    with ah_db.open_db_connection('pg') as conn:
        ingest_nativeapi_deploys(conn, datetime.datetime.now() - datetime.timedelta(29), datetime.datetime.now())
