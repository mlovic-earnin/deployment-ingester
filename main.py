import time
import datetime
import logging
import re
import sqlalchemy
import ah_config
import ah_db

import sys
sys.path.append('src/')
import datadog_events 
import deployments_db

def parse_jenkins_deploy_job_event(event):
    print(event)
    return {
        "deployed_at": datetime.datetime.fromtimestamp(event['date_happened'], datetime.timezone.utc),
        "is_rollback": False,
        "jenkins_event_title": event['title'],
        "datadog_event_id": event['id'],
        "jenkins_build_num": re.search('build #(\d+) ', event['title']).group(1),
    }


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
    deployments_db.upsert_deploys(conn, deploys)

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
    deployments_db.upsert_deploys(conn, deployments)

def query_earnin_standard_deployment_events(start_time, end_time):
    tags = [
        'deploy.environment:production',
        # TODO ingest non-success deploys?
        'deploy.progress:success'
    ]
    events = datadog_events.query(tags=tags,
                                  start_time=start_time,
                                  end_time=end_time)
    deploys = [parse_earnin_standard_deployment_events(event) for event in events]
    return deploys


if __name__ == "__main__":
    ah_config.initialize()

    datadog_events.initiatilize_datadog(
        api_key=ah_config.get("datadog_credentials.api_key"),
        app_key=ah_config.get("datadog_credentials.app_key")
    )

    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    with ah_db.open_db_connection('engineering_metrics') as conn:
        # TODO logging
        print("Connected to %s", conn.engine.url.__repr__())

        start = datetime.datetime.now() - datetime.timedelta(50)
        end   = datetime.datetime.now()

        # ingest_deployments(conn,
            # query_earnin_standard_deployment_events(start, end)
        # )
        deployments_db.upsert_deploys(conn,
            query_earnin_standard_deployment_events(start, end)
        )
