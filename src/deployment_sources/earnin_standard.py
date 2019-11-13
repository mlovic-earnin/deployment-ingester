"""This module queries the Datadog event stream for deployment events
which have a standard set of tags. This is the set of tags that are used
by deploy doctor, and that we are trying to standardize on at Earnin."""

import datetime
import datadog_events 

import logging
logger = logging.getLogger(__name__)

def query(start_time, end_time):
    tags = [
        'deploy.environment:production',
        # TODO ingest non-success deploys?
        'deploy.progress:success'
    ]
    events = datadog_events.query(tags=tags,
                                  start_time=start_time,
                                  end_time=end_time)
    logger.info("Received ({}) events".format(len(events)))

    deploys = [parse_deployment_event(event) for event in events]

    return deploys


def parse_deployment_event(event):
    # Destructure tag list into key-value pairs
    event_tags = dict((tag.split(':', 1)) for tag in event['tags'] if ':' in tag)
    # TODO add version tag? e.g. deploy.datadog_deploy_event_version:2

    return {
        # TODO set timestamp manually in tag from deploy script?
        "deployed_at":         datetime.datetime.fromtimestamp(event['date_happened'], datetime.timezone.utc),
        "is_rollback":         (event_tags.get('deploy.type') == 'rollback'),
        # TODO change this to datadog_event_title
        "jenkins_event_title": event['title'],
        "datadog_event_id":    event['id'],
        # TODO change "artifact" to "application" I think
        "artifact":            event_tags.get('deploy.application'),
        "initiator":           event_tags.get('deploy.initiator'),
        "release_tag":         event_tags.get('deploy.release'),
        "jenkins_build_num":   event_tags.get('deploy.jenkins.build_number'),
        "jenkins_job_name":    event_tags.get('deploy.jenkins.job_name'),
        "jenkins_build_url":   event_tags.get('deploy.jenkins.build_url'),
    }
