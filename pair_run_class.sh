#!/bin/bash
# Run tracing for a single class in a single project.

# Run container disconnected
image_name="benjijang/sf110:latest"
project="$1"
class="$2"
container_name="pair_${project}_$(echo $class | awk '{print tolower($0)}' | sed 's@/@.@g')"
docker run -d -v $PWD:/workspace -it --name "$container_name" "$image_name"
#docker exec "$container_name" bash -c "ls /workspace/tools/trace-modeling-tracers/trace_collection_java"
docker run "$container_name" bash "/workspace/install_deps.sh"
# Run unit test
docker exec "$container_name" bash "/workspace/pair_test.sh" "$project" "$class" &

# Run tracer
docker exec "$container_name" bash "/workspace/pair_trace.sh" "$project" "$class" &

# Both processes will wait on a timeout until both are initialized.
# Once each process initializes (expect to take only a few seconds), tracer will connect on port 8787.
# Tracing will start and conclude automatically.
wait

docker rm -f "$container_name"
