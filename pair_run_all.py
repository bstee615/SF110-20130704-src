
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
import sys
cwd = '.'
bash_command = """    
    project="$(echo $line | awk -F '[ \t]+' '{print $1}')"
    class="$(echo $line | awk -F '[ \t]+' '{print $2}')"
    bash """ + cwd + """/pair_run_class.sh "$project" "$class"  &
    wait
"""
async def run_command_async(command, timeout = None):
    print(f"running: {command}")
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
    new_line = '\n'
    print(f"finished running: {command.split(new_line)[0]}")
    return {
            "command": command,
            "stdout": stdout.decode('utf-8'),
            "stderr": stderr.decode('utf-8'),
            "returncode": proc.returncode,
        }

async def proc_one(args):
    print(args)
    command = f"line='{args['line']}'\n{bash_command}"
    args['output'][args['line']] = await run_command_async(command)
    return args["output"][args['line']]

async def run_batch_async(n_proc:int, output_location, foo, args:[], timeout_s:int = 60 * 5):
    tasks = []
    start = 0
    end = len(args)
    while len(tasks) < n_proc and start < end:
            tasks.append(asyncio.create_task(foo(args[start])))
            start += 1
    while len(tasks) > 0:
        try:
            # Wait for any task to complete or for a timeout
            done, pending = await asyncio.wait_for(
                asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED),
                timeout_s
            )
            for future in done:
                output = await future
                tasks.remove(future)
                if start < end:
                    tasks.append(asyncio.create_task(foo(args[start])))
                    start += 1
                print(json.dumps(output), file=output_location, flush=True)
        except asyncio.TimeoutError:
            if len(tasks) > 0:
                tasks[0].cancel()  # Cancel the first task (which is hopefully the oldest)
                try:
                    await tasks[0]  # Wait for the task to handle its cancellation
                except asyncio.CancelledError:
                    print("Cancelled the oldest ongoing task due to timeout.")
                tasks.pop(0)
            continue  

        #done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
async def main():
    parser = argparse.ArgumentParser()    
    parser.add_argument("--n_proc", type=int, default=10,
                        help="Number of processes to run in parallel")
    parser.add_argument("--timeout_m", type=int, default=3,
                        help="Number of processes to run in parallel")
    parser.add_argument("--class_list", default="classes_test.txt",
                            help="File with locations of projects, and class names to test as pairs on each line")
    cli_args = parser.parse_args()
    args = []
    output = {}
    timeout_s = round(cli_args.timeout_m * 60)
    with open(cli_args.class_list, 'r') as classes:
        for line in classes:
            args.append({"line":line, "output":output})
    await run_batch_async(cli_args.n_proc, sys.stdout, proc_one, args, timeout_s)


if __name__ == "__main__":
    asyncio.run(main())