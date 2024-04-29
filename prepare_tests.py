"""
This script runs "processing" actions on SF110 projects, mostly related to preaparing to run ant tasks or running EvoSuite.
"""

from pathlib import Path
import subprocess
import json
import shutil
import traceback
import pandas as pd
import tqdm
from multiprocessing import Pool, Value
import ctypes
from functools import partial
import argparse
from print_results import report_results
from xml.dom import minidom 
import asyncio
import os
#Translates this project's steps to ant commands
step_dict = {"evosuite-compile":["compile-evosuite"], "project-compile":["compile"]}
#port to run debugger/tracer on
tracer_port = Value(ctypes.c_int, 12500)  # Shared, synchronized integer
build_dir = ""

async def run_command_async(command, cwd, timeout = None):
    proc = await asyncio.create_subprocess_shell(command, 
        shell=True, 
        cwd=cwd, 
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    # read from stdout, and stderr asynchronously
    stdout_task = asyncio.create_task(proc.stdout.read())
    stderr_task = asyncio.create_task(proc.stderr.read())
    try:
        # Wait for the subprocess to finish, with timeout
        await asyncio.wait_for(proc.wait(), timeout)
    except asyncio.TimeoutError:
        print(f"Command '{command}' timed out after {timeout} seconds")
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
    # Ensure the process is terminated before exiting
    await proc.wait()
    # Ensure we capture the output
    stdout, stderr = await stdout_task, await stderr_task
    return {
            "command": command,
            "stdout": stdout.decode('utf-8'),
            "stderr": stderr.decode('utf-8'),
            "returncode": proc.returncode,
        }
async def prepare_one_project(t, args):
    _, group = t
    output = {}
    output["program"] = program = group["program"].iloc[0]
    cwd = f"{build_dir}{program}"
    def run_command_async_default_cwd(command, timeout = None):
        return run_command_async(command, cwd, timeout=timeout)

    class RunCommandException(Exception):
        """Report an error code resulting from running a command."""
        def __init__(self, result):
            super().__init__(f"Process {result['command']} exited with error code: {result['returncode']}")

    try:
        steps_to_skip = []
        #build.exe jvm arg to update
        if "clean" in args.steps:
            print("clean", program)
            steps_to_skip.append("clean")
            dirs_to_clean = ["evosuite-tests", "evosuite-report"]
            for dir in dirs_to_clean:
                test_dir = f"{cwd}/{dir}"
                if os.path.exists(test_dir):
                    shutil.rmtree(test_dir)
            output["clean"] = await run_command_async_default_cwd("ant clean")
    
        if "evosuite-generate" in args.steps:
            print("evosuite-generate", program)
            steps_to_skip.append("evosuite-generate")
            output["evosuite-generate"] = {classname: None for classname in group["class"]}
            classes = group["class"]
            if args.max_classes_per_project:
                classes = classes.head(args.max_classes_per_project)
            for classname in classes: # to limit execution time, limit to first 10 classes alphabetically
                output["evosuite-generate"][classname] = await run_command_async_default_cwd(f"java -jar ../lib/evosuite-1.0.6.jar -Dglobal_timeout {args.test_generation_timeout} -class {classname}")
        
        
        await asyncio.sleep(0)
        for step in args.steps:
            if step in steps_to_skip:
                continue
            print(step, program)

            # TODO: run existing project tests in step "project-test" so that debugger can attach to them

            #catch translation of generate_run step to many sf110 ant build step
            #from SF110 build.xml
            if step in step_dict:
                ant_commands = step_dict[step]
                for substep in ant_commands:
                    output_id = f"{step}: {substep}"
                    output[output_id] = await run_command_async_default_cwd(f"ant {substep}", timeout=args.test_run_timeout)
                    if output[output_id]["returncode"]:
                        raise RunCommandException(output[output_id])
            else: #default case to catch all build steps directly implemented in ant build
                #from SF110 build.xml
                output[step] = await run_command_async_default_cwd(f"ant {step}", timeout=args.test_run_timeout)
                if output[step]["returncode"]:
                    raise RunCommandException(output[step])
                
    except Exception as ex:
        output["error"] = {
            "message": str(ex),
            "stacktrace": traceback.format_exc(),
        }
    print("finished:", program)
    return output

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test_generation_timeout", type=int, default=60*2,
                        help="Maximum number of seconds to allow EvoSuite for test generation.")
    #parser.add_argument("--test_run_timeout", type=int, default=60*2,
    #                    help="Maximum number of seconds to allow EvoSuite for test execution.")
    parser.add_argument("--max_projects", type=int,
                        help="Maximum number of projects to process (sorted by ID ascending)")
    parser.add_argument("--max_classes_per_project", type=int,
                        help="Maximum number of classes to generate tests for per project (sorted lexicographically)")
    parser.add_argument("--nproc", type=int, default=4,
                        help="Number of processes to run in parallel")
    STEPS = ["clean", "project-compile", "evosuite-generate", "evosuite-compile", "evosuite-test"]
    SIMPLE_STEPS = ["clean", "evosuite-generate", "evosuite-compile"]
    JUST_TEST = ["evosuite-test"]
    parser.add_argument("--steps", type=str, nargs="+", default=SIMPLE_STEPS, choices=SIMPLE_STEPS,
                        help="Steps to run")
    args = parser.parse_args()

    # Load manifest of programs and classes
    with open("classes.txt") as f:
        classes = [tuple(l.strip().split()) for l in f.readlines()]
    build_dir = Path(".").absolute()
    df = pd.DataFrame(classes, columns=["program", "class"])
    df["program_no"] = df["program"].str.split("_").str[0].astype(int)
    df = df.sort_values(["program_no", "class"])
    if args.max_projects:
        df = df[df["program"].isin(df["program"].drop_duplicates(keep="first").head(args.max_projects))]
    print("Loaded manifest:")
    print(df)

    # Generate/run tests and write results to file
    dst_file = f"results_{','.join(args.steps)}.jsonl"
    
    with open(dst_file, "w") as f:
        g = df.groupby("program")
        groups = list(g)
        preparation_results = await async_parallel(args.nproc, prepare_one_project, groups, args)
        for result in preparation_results:
            print(json.dumps(result), file=f, flush=True)

    report_results(dst_file)
async def async_parallel(nproc, function, params_list, params_const):
    outputs = []
    tasks = []
    start = 0
    end = len(params_list)
    while len(tasks) < nproc and start < end:
        tasks.append(asyncio.create_task(function(params_list[start], params_const)))
        start += 1
    while len(tasks) > 0:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for future in done:
            outputs.append(await future)
            tasks.remove(future)
            if start < end:
                tasks.append(asyncio.create_task(function(params_list[start], params_const)))
                start += 1
    return outputs
if __name__ == "__main__":
    asyncio.run(main())