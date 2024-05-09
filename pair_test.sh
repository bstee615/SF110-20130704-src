#!/bin/bash

project="$1"
class="$2"
project_dir="workspace/$project"
cd $project_dir
#ant evosuite-test
class_name=$(echo $class | awk -F"." '{print $NF}')
ant evosuite-trace -Dtraced.classname="$class_name"
