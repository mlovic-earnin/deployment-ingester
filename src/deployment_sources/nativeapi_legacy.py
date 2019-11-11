import re
import datetime
import datadog_events 

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
def query(start_time, end_time):
    napi_job_name = 'nativeapi/prod.jobs/bld-stage-deploy'
    artifact_name = 'nativeapi'
    ingest_time   = datetime.datetime.now()

    events = datadog_events.query_jenkins_job_events(
        napi_job_name,
        start_time=start_time,
        end_time=end_time
    )
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

    return deploys
