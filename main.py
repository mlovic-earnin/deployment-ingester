import time
import datetime
import logging
import re
import sqlalchemy
import sqlalchemy.dialects.postgresql
import datadog
import ah_config
import ah_db


schema = 'engineering_metrics'
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
    schema=schema
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

# TODO error or warn or log on col mismatch
def upsert_deploys(conn, deploys):
    stmt = sqlalchemy.dialects.postgresql.insert(DEPLOYMENTS_TABLE)
    # TODO match on datadog event id instead?
    stmt = stmt.on_conflict_do_nothing(index_elements=['artifact', 'deployed_at'])
    print("Upserting ({}) deployments".format(len(deploys)))
    [print(d) for d in deploys]

    ingest_time = datetime.datetime.now()
    for deploy in deploys:
        deploy["ingested_at"] = ingest_time

    res = conn.execute(stmt, deploys)


def query_jenkins_job_events(job_name, start_time=None, end_time=None):
    return query_datadog_events(
        tags=[
            "job:{}".format(job_name),
            'result:success'
        ],
        sources='jenkins',
        start_time=start_time,
        end_time=end_time
    )


def query_datadog_events(tags=[], sources=None, start_time=None, end_time=None):
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
        last_30_days = query_datadog_events(
            tags=tags,
            start_time=(end_time - datetime.timedelta(batch_size)),
            end_time=end_time
        )
        # query rest
        rest = query_datadog_events(
            tags=tags,
            start_time=start_time,
            end_time=(end_time - datetime.timedelta(batch_size))
        )
        return [*rest, *last_30_days]


events = []
def ingest_legacy_nativeapi_deploys(conn, start_time, end_time):
    napi_job_name = 'nativeapi/prod.jobs/bld-stage-deploy'
    artifact_name = 'nativeapi'
    ingest_time   = datetime.datetime.now()

    events = query_jenkins_job_events(napi_job_name,
                                      start_time=start_time,
                                      end_time=end_time)
    print(events)
    print("Received ({}) events".format(len(events)))
    if len(events) == 1:
        print("Exiting")
        return
    deploys = [parse_jenkins_deploy_job_event(event) for event in events]
    for deploy in deploys:
        deploy.update({
            "artifact": artifact_name,
            "jenkins_job_name": napi_job_name
        })
    # TODO error or warn or log on col mismatch
    upsert_deploys(conn, deploys)

# TODO remove plural
def parse_earnin_standard_deployment_events(event):
    print(event)
    event_tags = dict((tag.split(':', 1)) for tag in event['tags'] if ':' in tag)
    # TODO deploy.datadog_deploy_event_version:1

    import pprint 
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(event_tags)

    return {
        # TODO set timestamp manually in tag from deploy script?
        "deployed_at":         datetime.datetime.fromtimestamp(event['date_happened'], datetime.timezone.utc),
        "is_rollback":         (event_tags.get('deploy.type') == 'rollback'),
        # TODO this is wrong
        "jenkins_event_title": event['title'],
        "datadog_event_id":    event['id'],
        # TODO change to "application" I think
        "artifact":            event_tags.get('deploy.application'),
        "initiator":           event_tags.get('deploy.initiator'),
        "release_tag":         event_tags.get('deploy.release'),
        "jenkins_build_num":   event_tags.get('deploy.jenkins.build_number'),
        "jenkins_job_name":    event_tags.get('deploy.jenkins.job_name'),
        "jenkins_build_url":   event_tags.get('deploy.jenkins.build_url'),
    }


def ingest_deployments(conn, deployments):
    # TODO this is not necessary...
    upsert_deploys(conn, deployments)

def query_earnin_standard_deployment_events(start_time, end_time):
    tags = [
        'deploy.environment:production',
        # TODO ingest non-success deploys?
        'deploy.progress:success'
    ]
    events = query_datadog_events(tags=tags,
                                  start_time=start_time,
                                  end_time=end_time)
    deploys = [parse_earnin_standard_deployment_events(event) for event in events]
    return deploys


if __name__ == "__main__":
    ah_config.initialize()

    datadog.initialize(api_key=ah_config.get("datadog_credentials.api_key"),
                       app_key=ah_config.get("datadog_credentials.app_key"))

    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    with ah_db.open_db_connection('engineering_metrics') as conn:
        # TODO logging
        print("Connected to %s", conn.engine.url.__repr__())

        start = datetime.datetime.now() - datetime.timedelta(50)
        end   = datetime.datetime.now()

        ingest_deployments(conn,
            query_earnin_standard_deployment_events(start, end)
        )
