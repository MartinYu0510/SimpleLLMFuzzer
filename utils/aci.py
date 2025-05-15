import re
import os
import time
import json
import yaml
import subprocess
import select
import threading
import signal
import psutil
import logging
import queue
import pty
from collections import deque
from datetime import datetime

# Load configuration variables
CONFIG_FILE = os.getenv("CONFIG_FILE")
WORIKING_DIR = os.getenv("WORKING_DIR")
PROJECT_DIR = os.getenv("PROJECT_DIR")

class ACI():
    """
    The Agent-Computer Interface class. This class should handle all communication with the docker container.
    """
    def __init__(self, logger: logging.Logger) -> subprocess.Popen:
        # Initialize global state variables
        self.open_file = "n/a"
        self.working_dir = WORIKING_DIR
        self.config_file = CONFIG_FILE
        self.config = None
        self.logger = logger
        self.timeout = False
        self.master_fd = None
        self.slave_fd = None

        # Define initialize command
        self.init_cmd = ""

        # Load the configs from the `config.yaml` file.
        self.load_config(self.config_file)

        # Initialize the ACI
        self.container = self.init_aci()

    def load_config(self, config_file: str):
        """
        Load the configs from the `config.yaml` file.
        """
        # Read the config file
        try:
            with open(config_file, 'r') as file:
                self.config = yaml.safe_load(file)
        except:
            raise FileNotFoundError("The config file does not exist!")

        # Load environment variables
        env_variables = self.config.get('env_variables', {})
        export_cmd = ""
        if env_variables:
            for sub_key, sub_value in env_variables.items():
                locals()[sub_key] = sub_value
                export_cmd += f"export {sub_key}={sub_value}\n"
        else:
            raise ValueError("No environment variables found in the config file!")

        # Load ACI bash tools initialization commands
        if self.config.get('docker', True):
            scripts = self.config.get('command_files_absolute', [])
        else:
            scripts = self.config.get('command_files_opposite', [])

        if scripts:
            source_cmd = ""
            for item in scripts:
                source_cmd += f"source {item}\n"
        else:
            raise ValueError("No scripts found in the config file!")
        
        # Load the state command
        state_command = self.config.get('state_command')["code"]
        if not state_command:
            raise ValueError("No state command found in the config file!")
        
        self.init_cmd = f"{export_cmd}\n{source_cmd}\nalias ls='ls -F'\n{state_command}\ncd {self.working_dir}\n"

    def extract_action_and_input(self, text: str) -> (str):
        """
        Extract the action and input from LLM's reply.
        """
        action_pattern = r"Action: (.+?)\n"
        input_pattern = r'Action_Input: ##([\s\S]*?)##'
        
        action = re.search(action_pattern, text)
        action = action.group(1) if action else None
        action_input = re.search(input_pattern, text)
        action_input = action_input.group(1) if action_input else None

        if action and action_input:
            return action, action_input
        else:
            return "Error", "Format error"

    def read_from_fd(self, fd, timeout: int | float = 10) -> bytes:
        """ 
        Read data from a subprocess with a timeout.
        This function uses a file descriptor to read data from the subprocess in a non-blocking way.
        """
        data = b""
        start_time = time.time()
        while True and time.time() - start_time < timeout:
            ready, _, _ = select.select([fd], [], [], timeout / 2.0)
            if fd in ready:
                part = os.read(fd, 4096)  # Read in chunks to handle large outputs
                if not part:
                    break
                data += part
            else:
                # If timeout is specified, and no data is ready, break
                if timeout and time.time() - start_time > timeout:
                    break
        return data
    
    def update_state(self, container: subprocess.Popen):
        """
        Read the state of the container and update global variables.
        """
        self.read_from_fd(self.master_fd, 0.1) # Flush the `stdout pipe
        _, ready_to_write, _ = select.select([], [container.stdin.fileno()], [], 5)
        if ready_to_write:
            container.stdin.write("state\n")
            container.stdin.flush()
        else:
            self.logger.info("Timeout occurred while updating state.")
        state = self.read_from_fd(self.master_fd, 0.5)
        # logger.info(f"Updating State......\n{state.decode()}")

        try:
            state = json.loads(state)
            self.open_file = state['open_file']
            self.working_dir = state['working_dir']
            # logger.info(f"Updated State\nopen_file: {open_file}\nworking_dir: {working_dir}")
        except:
            # logger.info(f"State update failed!\n")
            pass

    def clean_ansi_codes(self, input: str) -> str:
        """
        Clean ANSI control sequences from the given input string and return the cleaned text.
        """
        ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        cleaned_text = ansi_escape.sub('', input)
        return cleaned_text

    def read_latest_tui_output(self) -> str:
        """
        Read the latest output from the child process's `stdout`.
        """
        self.read_from_fd(self.master_fd, 0.5) # Flush the `stdout` PIPE of the container
        time.sleep(0.3) # Wait for newest TUI outputs
        latest_output = self.clean_ansi_codes(self.read_from_fd(self.master_fd, 0.1).decode()) # Read the latest output from the `stdout`
        
        return latest_output

    def kill_process(self, pid: int) -> int:
        """
        Kill the given process.
        """
        self.logger.info("Command timed out. Trying to kill the process......")
        try:
            if pid > 0:
                self.logger.info("Terminating the process...")
                os.kill(pid, signal.SIGTERM)
            else:
                self.logger.info(f"The process with PID {pid} does not exist.")
                return 1
            try:
                subprocess.check_output(["ps", "-p", str(pid)])
                os.kill(pid, signal.SIGKILL)
                self.logger.info("Terminating the process failed, killing the process...")
                return 1
            except subprocess.CalledProcessError:
                self.logger.info("The process has been terminated.")
                return 1
        except ProcessLookupError:
            self.logger.warning(f"The process with PID {pid} does not exist.")
            return 0
        except Exception as e:
            self.logger.error(f"Error while killing the process with PID {pid}: {e}")
            return 0

    def get_child_pid(self, bash_pid: int) -> int:
        """
        Get child PID using psutil.
        """
        try:
            parent = psutil.Process(bash_pid)
            children = parent.children(recursive=False)
            if children:
                return children[0].pid
            else:
                return -1
        except psutil.NoSuchProcess:
            self.logger.info(f"No process with PID {bash_pid} exists.")
            return -1
        
    def kill_process_tree(self, pid: int):
        """
        Kill the given process and all its children.
        """
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                os.kill(child.pid, signal.SIGTERM)
            os.kill(pid, signal.SIGKILL)
        except psutil.NoSuchProcess:
            self.logger.info(f"No process with PID {pid} exists.")

    def init_aci(self) -> subprocess.Popen:
        """
        Initialize the ACI and return a Popen object.
        """
        self.master_fd, self.slave_fd = pty.openpty()
        container = subprocess.Popen(
            "/bin/bash",
            stdin=subprocess.PIPE,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            text=True, 
            bufsize=1,
        )
        container.stdin.write(self.init_cmd + "\n")
        container.stdin.flush()
        self.read_from_fd(self.master_fd, 1) # Flush the `stdout` pipe

        return container
    def observate_terminal(self, timeout: int | float = 5) -> str:
        """
        Get the subprocess's bash terminal outputs.
        """
        output = self.clean_ansi_codes(self.read_from_fd(self.master_fd, timeout).decode())
        return output

    def run_command_with_timeout(self, container: subprocess.Popen, command: str, timeout: float = 0, update: bool = True) -> (str):
        """
        Function calling of the agent, to run a given command in the container's bash terminal.
        """
        _, ready_to_write, _ = select.select([], [container.stdin.fileno()], [], 5)
        if ready_to_write:
            from planning.prompt import Next_step_no_output_template, Command_timeout_message
            self.timeout = False
            command = command if command.endswith("\n") else command + "\n"
            output = ""
            exit_code = "0"
            if not timeout:
                timeout = self.config.get('env_variables')["COMMAND_TIMEOUT"]
            # Runs the command `command` in the shell whose handle is `container`.
            # Returns the exit code of `command`.
            # This must be different from all lines of output from the command `command`.
            SENTINEL = "UNIQUE_SENTINEL"
            # This must be different from all environment variables in the shell.
            SAVED_CODE = "UNIQUE_ENVIRONMENT_VARIABLE"
            # 1. Runs `command` with a timeout
            # 2. Saves the exit code
            # 3. Echos the sentinel
            if timeout > 0:
                container.stdin.write(f"{command}{SAVED_CODE}=$?\necho {SENTINEL}\n")
                container.stdin.flush()
                bash_pid = container.pid
                command_pid = self.get_child_pid(bash_pid)
                def wrapper(*args):
                    kill_exit_code = self.kill_process(*args)
                    if kill_exit_code == 1:
                        self.timeout = True
                timer = threading.Timer(timeout, wrapper, args=(command_pid,))

                try:
                    timer.start()
                    with os.fdopen(self.master_fd, 'r', closefd=False) as master:
                        for line in iter(master.readline, ''):
                            if SENTINEL in line:
                                container.stdin.write(f"echo ${SAVED_CODE}\n")
                                container.stdin.flush()
                                exit_code = master.readline().strip()
                                break
                            output += line.strip() + '\n'
                            if self.timeout:
                                break
                    timer.cancel()
                except:
                    timer.cancel()

                timer.cancel()
            else:
                container.stdin.write(f"{command}\n{SAVED_CODE}=$?\necho {SENTINEL}\n")

                with os.fdopen(self.master_fd, 'r', closefd=False) as master:
                    for line in iter(master.readline, ''):
                        if SENTINEL in line:
                            container.stdin.write(f"echo ${SAVED_CODE}\n")
                            container.stdin.flush()
                            exit_code = master.readline().strip()
                            break
                        output += line.strip() + '\n'
            
            # Check if the command runs timeout
            if self.timeout:
                output = self.clean_ansi_codes(output)
                self.logger.info(f"Command timed out. Output:\n{self.clean_ansi_codes(output)}")
                output += Command_timeout_message.format(open_file=self.open_file, working_dir=self.working_dir)
                exit_code = "1"
                self.timeout = False
            # Replace the output with a default message if it's empty
            if output == "" and exit_code == "0":
                output = Next_step_no_output_template.format(open_file=self.open_file, working_dir=self.working_dir)
            # logger.info(f"Command\nCommand:\n{command}\nOutput:\n{output}")
            # logger.info(f"State\nopen_file: {self.open_file}\nworking_dir: {self.working_dir}")

            # Get the latest lines of output
            lines = output.splitlines()
            last_lines = lines[-os.environ.get("OUTPUT_LINES", 100):]
            output = "\n".join(last_lines)
            output = self.clean_ansi_codes(output)

            # Update the state of the container
            if update and not self.timeout:
                self.update_state(container)
        
            return output, exit_code
        
        else:
            fail_msg = "The command failed to run since the interface is not ready to write."
            return fail_msg, "1"

    def run_command_non_blocking(self, container: subprocess.Popen, command: str, timeout: float = 5, update: bool = True) -> str:
        """
        Run a given command in non-blocking mode and return the output to look for if a persistent commands runs successfully.
        """
        # Use the command
        command = command if command.endswith("\n") else command + "\n"
        _, ready_to_write, _ = select.select([], [container.stdin.fileno()], [], 5)
        if ready_to_write:
            container.stdin.write(command)
            container.stdin.flush()

            # Read from stdout in 5 seconds
            from planning.prompt import Next_step_no_output_template
            output = self.observate_terminal(timeout)
            
            if output == "":
                output = Next_step_no_output_template.format(open_file=self.open_file, working_dir=self.working_dir)
            # logger.info(f"Command\nCommand:\n{command}\nOutput:\n{output}")
            # logger.info(f"State\nopen_file: {self.open_file}\nworking_dir: {self.working_dir}")

            # Get the latest lines of output
            lines = output.splitlines()
            last_lines = lines[-os.environ.get("OUTPUT_LINES", 100):]
            output = "\n".join(last_lines)

            # Update the state of the container
            if update:
                self.update_state(container)
            
            return output
        else:
            fail_msg = "The command failed to run since the container is not ready to write."
            return fail_msg

    def get_project_structure(self, working_dir: str) -> str:
        """
        Get the tree structure of the project using `tree` command.
        """

        result = subprocess.run(
                ['/bin/bash', '-c', f'cd {working_dir}; tree -d -F'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, 
                text=True
            )
        result = result.stdout
        tree = self.clean_ansi_codes(result)

        return tree
