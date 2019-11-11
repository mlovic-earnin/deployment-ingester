import datetime
import datadog_events 

def query(start_time, end_time):
    tags = [
        'deploy.environment:production',
        # TODO ingest non-success deploys?
        'deploy.progress:success'
    ]
    events = datadog_events.query(tags=tags,
                                  start_time=start_time,
                                  end_time=end_time)
    deploys = [parse_deployment_event(event) for event in events]
    return deploys


def parse_deployment_event(event):
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

