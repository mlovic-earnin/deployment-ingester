#!/bin/sh

docker_repo=artifacts.k8s.us-west-2.dev.earnin.com:8082
image_name=deployment-ingester 
docker build --build-arg NEXUS_PASSWORD=$NEXUS_PASSWORD --build-arg NEXUS_USER=ci -t $docker_repo/$image_name .

docker push $docker_repo/$image_name
