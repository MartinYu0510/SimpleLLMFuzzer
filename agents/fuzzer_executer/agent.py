import os
import openai
from openai import OpenAI
from planning.prompt import *
from planning.history_processor import *
from utils.aci import *
from utils.log import *
from agents.fuzzer_executer.prompt import *
import re
from datetime import datetime
import time


# Define the main agent loop
def run_executer():
    """
    Run the executor agent to manage and optimize fuzzer execution.
    """
    crash_detected_flag = False
    retries = 0

    # Load OpenAI API key and OpenAI API base URL from environment variables
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")

    # Define LLM
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
    # Define logger
    logger = get_logger("Executer Agent")
    logger.info("Executer agent started.")
    # Define ACI environment
    aci = ACI(logger)
    # Define history processor
    history_processor = HistoryProcessor(logger)

    # Load the configurations from the `config.yaml` file.
    try:
        with open(CONFIG_FILE, 'r') as file:
            yaml_data = yaml.safe_load(file)
    except:
        raise FileNotFoundError("The config file does not exist!")

    llm_args = yaml_data.get('llm_args', {})
    for sub_key, sub_value in llm_args.items():
        locals()[sub_key] = sub_value
    
    if yaml_data.get('docker', True):
        agent_outputs = yaml_data.get('agent_outputs_absolute')
        for sub_key, sub_value in agent_outputs.items():
            locals()[sub_key] = sub_value
    else:
        agent_outputs = yaml_data.get('agent_outputs_opposite')
        for sub_key, sub_value in agent_outputs.items():
            locals()[sub_key] = sub_value

    # Prepare the initial message
    epoch = 0
    global_speed = 0
    global_crashes = 0
    global_coverage = 0.0
    role_prompt = Role_prompt.format(WINDOW=str(aci.config.get('env_variables')["WINDOW"]))
    action_prompt = Action_prompt.format(COMMAND_TIMEOUT=str(aci.config.get('env_variables')["COMMAND_TIMEOUT"]))
    system_prompt = Common_system_prompt.format(Role_prompt=role_prompt, command_docs=command_docs, actions=action_prompt, open_file=aci.open_file, working_dir=aci.working_dir)
    prompt = Instant_prompt.format(working_dir=aci.working_dir, open_file=aci.open_file, fuzzers=fuzzers, optional_msg="", project_structure=aci.get_project_structure(aci.working_dir))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    logger.info(f"Query\nSystem Prompt:\n{system_prompt}\nUser Prompt:\n{prompt}")

    # Agent main loop
    main_flag = True
    response_format_error_flag = False
    curr_time = datetime.now().minute
    while main_flag:
        retry = 0
        while retry < 3:
            try:
                response = client.chat.completions.create(model=locals()['LLM_MODEL'], messages=messages, temperature=locals()['LLM_TEMPERATURE'], timeout=locals()['LLM_REPLY_TIMEOUT'])
                logger.info(f"Response Tokens\nCompletion Tokens:{response.usage.completion_tokens}\nPrompt Tokens:{response.usage.prompt_tokens}\nTotal Tokens:{response.usage.total_tokens}")
                break
            except openai.APITimeoutError:
                logger.warning("LLM API Query Timed Out. Retrying......")
                retry += 1
            if retry == 3:
                main_flag = False
                logger.error("LLM API Query Timed Out. Exiting......")
                break
        
        epoch += 1
        response_text = response.choices[0].message.content
        logger.info(f"Epoch{epoch} Answer\n{response_text}")
        epoch_prompt = Epoch_message.format(epoch=epoch)

        # Action
        action, action_input = aci.extract_action_and_input(response_text)
        logger.info(f"Action and Input\nAction: {action}\nInput: {action_input}")

        if action == "Use_Command":
            response_format_error_flag = False
            observation, exit_code = aci.run_command_with_timeout(aci.container, action_input.strip(), aci.config.get('env_variables')["COMMAND_TIMEOUT"])
            content = f"Observation: {observation}\nExit Code: {exit_code}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})" + epoch_prompt + Self_critic_message
            history_processor.extend_msg(messages, response_text, content)
        elif action == "Observe_Terminal":
            response_format_error_flag = False
            observation = aci.observate_terminal()
            content = f"Observation: {observation}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})" + epoch_prompt + Self_critic_message
            history_processor.extend_msg(messages, response_text, content)
        elif action == "Run_Fuzzer":
            response_format_error_flag = False

            observation, exit_code = aci.run_command_with_timeout(
                aci.container, action_input.strip(), timeout=-1, update=False
            )

            epoch_prompt = Epoch_message.format(epoch=epoch)

            if exit_code == "1" and "AddressSanitizer" in observation:
                logger.warning("Detected immediate crash (AddressSanitizer). Trying to continue fuzzing...")

                # Modify command to add fork and ignore crashes
                if "-fork=" not in action_input and "-jobs=" not in action_input:
                    updated_cmd = action_input.strip() + " -fork=1 -ignore_crashes=1"

                    crash_message = (
                        f"Immediate crash detected.\n"
                        f"Modified command to continue fuzzing: `{updated_cmd}`\n"
                        f"Saving crashing input if available.\n"
                        f"{epoch_prompt}"
                    )
                    history_processor.extend_msg(messages, response_text, crash_message)

                    # Insert a synthetic user command to retry
                    messages.append({
                        "role": "user",
                        "content": f"Please re-run the fuzzer with: ##{updated_cmd}##"
                    })
                    continue  # Skip epoch increment

                    # Otherwise normal behavior
                content = f"Fuzzer Run Output:\n{observation}\n{epoch_prompt}"
                history_processor.extend_msg(messages, response_text, content)

        elif action == "Check_Fuzzer":
            response_format_error_flag = False
            observation = aci.read_latest_tui_output()
        
            # quick extraction helpers
            speed  = re.findall(r'exec\/s\s*:\s*(\d+)', observation)
            paths  = re.findall(r'paths\s*:\s*(\d+)', observation)
            crash  = re.findall(r'crashes\s*:\s*(\d+)', observation)
        
            content = (
                f"Fuzzer Status\n"
                f"Exec/s : {speed[-1] if speed else 'NA'}\n"
                f"Paths  : {paths[-1] if paths else 'NA'}\n"
                f"Crashes: {crash[-1] if crash else '0'}\n\n"
                f"RAW:\n{observation}\n"
                + epoch_prompt
            )
            history_processor.extend_msg(messages, response_text, content)

            
        elif action == "Adjust_Fuzzer":
            response_format_error_flag = False

            if crash_detected_flag and retries > 2:
                logger.warning("Multiple crashes even after -ignore_crashes. Suggest rebuilding without ASan.")

                rebuild_message = (
                    "Persistent crashes detected.\n"
                    "Suggestion: Rebuild the target binary without AddressSanitizer, "
                    "keeping only `-fsanitize=fuzzer` instrumentation.\n"
                    "After rebuild, restart fuzzing."
                )
                history_processor.extend_msg(messages, response_text, rebuild_message)

            else:
                # Normal adjust logic
                adjust_output = aci.run_command_non_blocking(aci.container, action_input.strip(), timeout=10, update=False)
                content = f"Adjust Fuzzer Output:\n{adjust_output}\n{epoch_prompt}"
                history_processor.extend_msg(messages, response_text, content)

        elif action == "Respond_to_Human":
            logger.info(f"Final Result: {action_input}")
            output_file = locals()['executer_output_file']
            with open(output_file, 'w') as f:
                f.write(action_input)
            aci.kill_process_tree(aci.container.pid)
            aci.container.terminate()
            return action_input
        elif action == "Summarize_Agent":
            response_format_error_flag = False
            logger.info(f"Agent Summary:\n{action_input}")
            aci.kill_process_tree(aci.container.pid)
            aci.container.terminate()
            return action_input
        else:
            logger.error("Error handling......")


    aci.kill_process_tree(aci.container.pid)
    aci.container.terminate()