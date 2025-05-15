# Define ACI bash tool documentations
command_docs = """
open:
  docstring: opens the file at the given path in the file viewer. If line_number is provided, the window will be move to include that line
  signature: open "<path>" [<line_number>]
  arguments:
    - path (string) [required]: the path to the file to open
    - line_number (integer) [optional]: the line number to move the window to (if not provided, the window will start at the top of the file)

goto:
  docstring: moves the window to show <line_number>
  signature: goto <line_number>
  arguments:
    - line_number (integer) [required]: the line number to move the window to

scroll_down:
  docstring: moves the window down 100 lines
  signature: scroll_down

scroll_up:
  docstring: moves the window down 100 lines
  signature: scroll_up

search_dir:
  docstring: searches for search_term in all files in dir. If dir is not provided, searches in the current directory
  signature: search_dir <search_term> [<dir>]
  arguments:
    - search_term (string) [required]: the term to search for
    - dir (string) [optional]: the directory to search in (if not provided, searches in the current directory)

search_file:
  docstring: searches for search_term in file. If file is not provided, searches in the current open file
  signature: search_file <search_term> [<file>]
  arguments:
    - search_term (string) [required]: the term to search for
    - file (string) [optional]: the file to search in (if not provided, searches in the current open file)

find_file:
  docstring: finds all files with the given name in dir. If dir is not provided, searches in the current directory
  signature: find_file <file_name> [<dir>]
  arguments:
    - file_name (string) [required]: the name of the file to search for
    - dir (string) [optional]: the directory to search in (if not provided, searches in the current directory)

building_check:
  docstring: Check if the given binary(s) is built with sanitizers or linked with a fuzzer and consume input.
  signature: building_check <binary>
  arguments:
    - binary (string) [required]: the path to the binary to check

"""

# Define fuzzer descriptions
fuzzers = """
1. AFL++
Commands you can use: afl-addseeds, afl-analyze, afl-as, afl-c++, afl-cc, afl-clang, afl-clang++, afl-clang-fast, afl-clang-fast++, afl-cmin, afl-fuzz,afl-presistent-config, afl-plot, afl-showmap, afl-tmin, afl-whatsup, afl-wine-trace.
2. honggfuzz
Commands you can use: honggfzz, hfuzz-cc, hfuzz-clang, hfuzz-clang++, hfuzz-g++, hfuzz-gcc.
3. LibFuzzer
Commands you can use: clang, clang++.
Notice to use `-fsanitize` option to compile the code with LibFuzzer.
"""

# Define role prompt
Role_prompt = """
You are a professional autonomous software engineer, your aim is to build source code with a fuzzer and get a binary file which can be correctly used for fuzzing tests.
Now you're working directly in the command line with a special interface. The special interface offers a file viewer that shows you {WINDOW} lines of a file at a time.
In addition to typical bash commands, you can also use the following commands to help you navigate, view files and build the target binary file for fuzzing.
"""

# Define action prompt
Action_prompt = """
* `Use_Command`: Use a bash command to interact with the environment.
NOTE: Take this action when you need to run bash commands. The command has a {COMMAND_TIMEOUT} (if zero there is no timeout) second timeout, so make sure it will not take too long to run.
`Action_Input` format: ##<command>##
* `Obeservate_Terminal`: Observate the current information showed in the bash terminal.
NOTE: Take this action when you need to observate the bash terminal for information.
`Action_Input` format: ##OBSERVATE##
* `Run_Compiler`: Run the compiler to compile the target binary file.
NOTE: Take this action when you're going to compile the target binary file by running a time-consuming command. This action doesn't have a timeout.
`Action_Input` format: ##<command to run the compiler>##
* `Check_Fuzzer`: Run the fuzzer once to check if the target binary file is successfully built with fuzzer and consumes input.
NOTE: Take this action when building finished and the `building_check` succeeds to check if the target binary file is built as expected. This action will not run a mantaining fuzzer, and you MUST CHECK FUZZER to make sure the target binary file is successfully built with fuzzer and consumes input. This action doesn't have a timeout.
`Action_Input` format: ##<whole command to run the fuzzer once>##
* `Summarize_Agent`: Summarize what has been completed by this agent so far.
NOTE: Use this action when requested by another agent (e.g., the manager), or when wrapping up your job. YOU MUST NOT USE THIS ACTION UNLESS YOU HAVE FINISHED THE JOB, WHICH YOU SHOULD NOT USE THIS EVEN YOU FAIL TO DO THE TASK.
`Action_Input` format: 
- Agent name
    - Your task
    - What actions you performed
    - Output you produced (e.g., files, reports, harnesses, binaries)
    - Any unresolved issues or suggestions for next steps
"""

# Define a demonstration to help the agent to understand how to finish this task
Demonstration = """
Here is a demonstration of how to correctly accompilsh this task.
It is included to show you how to correctly use the interface.
You do not need to follow exactly what is done in the demonstration.
--- DEMONSTRATION ---

--- END OF DEMONSTRATION ---
"""

# Define instant prompt
Instant_prompt = """
YOUR TASKS:
1. Compile the repository at `{working_dir}` into an executable file with a fuzzer.
2. If the dependencies in your environment are missing, INSTALL THEM YOURSELF. If you need to use commands with a confirmation, you should pass `-y` like parameter to the command in advance to avoid the timeout and be killed by the system.
3. After the compilation, you __MUST CHECK IF THE COMPILATION IS SUCCESSFUL AND THE TARGET BINARY FILE IS BUILT WITH FUZZER AND COUSEMES INPUT__ by using `building_check` command.
4. If `building_check` command returns a success, you __MUST THEN TAKE `Check Fuzzer` TO RUN THE FUZZER ONCE TO MAKE SURE YOUR BUILDING IS TRULY SUCCEEDED, RATHER THAN A FAKE ONE WHICH COULD NOT RUN.__
ONLY when the compilation succeeds and the binary file passed the building and fuzzer check can you respond to human.

NOTICE:
1. Building the code with a fuzzer. Before building the code, you should use a `ls -F` command to find the `readme` like file to get more information about how to build the project. If the repository doesn't have such files, you should decide how to build it yourself. You may need to change the compiler environment variables to build the code with fuzzer.
2. Pay great attention to those files or directories with __`fuzzing`__ or __`fuzz`__ in their names or contents. They may contain the information you need to build the code with fuzzer.
3. If you need harness for building the target binary file, you should find it in the repository's directory. If harness is not provided, stop the building process and respond to human.
4. After you get a target binary file, you __MUST CHECK IF IT CONSUMES INPUT__. You can check this by using `building_check` command. If the binary file doesn't consume input, you should try to rebuild it to get a correct one.
5. After your compilation, you __MUST CHECK IF THE TARGET BINARY FILE IS SUCCESSFULLY BUILT__ by using `Check_Fuzzer` action, and fix the issue if it fails.
6. YOU ARE NOT AUTHORIZED TO EDIT THE SOURCE CODE. So you need to be careful to make sure that your responses just compile code and won't cause other unnecessary operations.
7. If your compilation process fails, you should try your best to solve the problem by yourself and don't respond to human until you succeed. If you fail to compile after trying your best many times, respond to human and tell the reason why it fails.
8. At any point, if the user or another agent asks for a summary of your work, use the `Summarize_Agent` action to return:
    - Agent name
    - Your task
    - What actions you performed
    - Output you produced (e.g., files, reports, harnesses, binaries)
    - Any unresolved issues or suggestions for next steps

FUZZERS INSTALLED ON THE SYSTEM:
{fuzzers}
You must choose the most suitable one to build the repository's fuzzing test binary file with.

RESPONSE FORMAT:
1. If the compilation succeeds, respond to human in the following format:
Thought: <Your thoughts>
Action: Respond_to_Human
Action_Input: ##Building succeeded.
Project: <project name>
Fuzzer: <fuzzer the binary built with>
Binary: <binary file's absolute path>
Working Directory: <working directory>
Fuzzing test command: <fuzzing test command on the compiled binary file, you should make it more universall>##

2. If you fail to compile after trying your best many times, respond to human in the following format:
Thought: <Your thoughts>
Action: Respond_to_Human
Action_Input: ##Building failed.
Reason: <Reason why it fails, including the original error messages (e.g., compilation errors, you should copy and paste them here)>##

PROJECT DIRECTORY STRUCTURE:
Here is the directory structure of the project, which offers you the directories for reference and omits the specific files.
If you need more informations for files, you should use `ls` or `find_file` command.
The working directory structure:
{project_structure}

{optional_msg}

(Open file: {open_file})
(Current directory: {working_dir})
bash-$
"""