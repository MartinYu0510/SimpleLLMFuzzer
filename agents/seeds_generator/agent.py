import os
import openai
from openai import OpenAI
from planning.prompt import *
from planning.history_processor import *
from utils.aci import *
from utils.log import *
from agents.seeds_generator.prompt import *
from datetime import datetime
import time

# Define the main agent loop
def run_seed_generator(input_msg: str = None):
    """
    Run the seed generation agent.
    """
    # Load OpenAI API key and OpenAI API base URL from environment variables
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")

    # Define LLM client
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
    # Define logger
    logger = get_logger("Seed Generator Agent")
    logger.info("Seed Generator agent started.")
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
    role_prompt = Role_prompt.format(WINDOW=str(aci.config.get('env_variables')["WINDOW"]))
    action_prompt = Action_prompt.format(COMMAND_TIMEOUT=str(aci.config.get('env_variables')["COMMAND_TIMEOUT"]))
    system_prompt = Common_system_prompt.format(Role_prompt=role_prompt, command_docs=command_docs, actions=action_prompt, open_file=aci.open_file, working_dir=aci.working_dir)
    prompt = Instant_prompt.format(working_dir=aci.working_dir, open_file=aci.open_file, fuzzers=fuzzers, optional_msg="", project_structure=aci.get_project_structure(aci.working_dir))

    if not input_msg:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        logger.info(f"Query\nSystem Prompt:\n{system_prompt}\nUser Prompt:\n{prompt}")
    else:
        prompt = Instant_prompt.format(working_dir=aci.working_dir, open_file=aci.open_file, fuzzers=fuzzers, optional_msg=input_msg, project_structure=aci.get_project_structure(aci.working_dir))
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
        # Avoid exceeding rate limits by controlling LLM queries
        if epoch % 10 == 0:
            prev_time = curr_time
            curr_time = datetime.now().minute
            if curr_time - prev_time < 1:
                time.sleep((curr_time - prev_time) * 60)

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
        logger.info(f"Epoch {epoch} Answer\n{response_text}")
        epoch_prompt = Epoch_message.format(epoch=epoch)

        # Action Handling
        action, action_input = aci.extract_action_and_input(response_text)
        logger.info(f"Action and Input\nAction: {action}\nInput: {action_input}")

        if action == "Use_Command":
            response_format_error_flag = False
            observation, exit_code = aci.run_command_with_timeout(aci.container, action_input.strip(), aci.config.get('env_variables')["COMMAND_TIMEOUT"])
            if exit_code == "0":
                content = f"Observation: Your command ran successfully with exit code {exit_code}.\n{observation}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})\nbash-$" + epoch_prompt + Self_critic_message
                history_processor.extend_msg(messages, response_text, content)
            else:
                content = f"Observation: Your command failed with exit code {exit_code}.\n{observation}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})\nbash-$" + epoch_prompt + Self_critic_message
                history_processor.extend_msg(messages, response_text, content)
        
        elif action == "Identify_Input_Type":
            response_format_error_flag = False
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 5, update=False)
            content = f"Input Type Identified: {observation}\n" + epoch_prompt
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Generate_Seeds":
            response_format_error_flag = False
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 10, update=False)
            content = f"Generated Seeds:\n{observation}\n" + epoch_prompt
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Store_Seeds":
            response_format_error_flag = False
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 5, update=False)
            content = f"Seeds stored successfully.\n" + epoch_prompt
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Optimize_Seeds":
            response_format_error_flag = False
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 10, update=False)
            content = f"Seed Optimization Completed:\n{observation}\n" + epoch_prompt
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Respond_to_Human":
            response_format_error_flag = False
            logger.info(f"Response: {action_input}")
            output_file = locals()['seed_generator_output_file']
            with open(output_file, 'w') as file:
                file.write(action_input)
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
            if not response_format_error_flag:
                history_processor.record_history(messages)
            response_format_error_flag = True
            content = Error_message.format(open_file=aci.open_file, working_dir=aci.working_dir) + epoch_prompt + Self_critic_message
            history_processor.extend_msg(history_processor.history, response_text, content)

    aci.kill_process_tree(aci.container.pid)
    aci.container.terminate()

