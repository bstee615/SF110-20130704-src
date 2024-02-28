#!/bin/bash
# Run tracing for all projects, all classes.

while read line
do
    project="$(echo $line | awk -F '[ \t]+' '{print $1}')"
    class="$(echo $line | awk -F '[ \t]+' '{print $2}')"
    class="$(echo $class | sed 's@\.@/@g')" # Convert class name to class filepath
    bash $(dirname $0)/pair_run_class.sh "$project" "$class"
done < classes.txt
