#!/bin/bash

project="$1"
class="$2"

project_dir="$(dirname $0)/$project"

cd $project_dir
ant evosuite-trace -Dtraced.classname="$class"
