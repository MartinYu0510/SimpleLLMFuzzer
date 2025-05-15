import os
import openai
from openai import OpenAI
from planning.prompt import *
from planning.history_processor import *
from utils.aci import *
from utils.log import *
from agents.harness_generator.prompt import *
from datetime import datetime
import time

def run_harness_generator(input_msg: str = None):
    """
    Run the harness generation agent.
    """
    # Load OpenAI credentials
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
    logger = get_logger("Harness Generator Agent")
    logger.info("Harness Generator agent started.")
    aci = ACI(logger)
    history_processor = HistoryProcessor(logger)

    # Load config
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

    # Setup prompt
    epoch = 0
    role_prompt = Role_prompt.format(WINDOW=str(aci.config.get('env_variables')["WINDOW"]))
    action_prompt = Action_prompt.format(COMMAND_TIMEOUT=str(aci.config.get('env_variables')["COMMAND_TIMEOUT"]))
    system_prompt = Common_system_prompt.format(Role_prompt=role_prompt, command_docs=command_docs, actions=action_prompt, open_file=aci.open_file, working_dir=aci.working_dir)
    prompt = Instant_prompt.format(working_dir=aci.working_dir, open_file=aci.open_file, fuzzers=fuzzers, optional_msg=input_msg or "", project_structure=aci.get_project_structure(aci.working_dir))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    logger.info(f"Query\nSystem Prompt:\n{system_prompt}\nUser Prompt:\n{prompt}")

    # Main agent loop
    main_flag = True
    response_format_error_flag = False
    curr_time = datetime.now().minute
    while main_flag:
        if epoch % 10 == 0:
            prev_time = curr_time
            curr_time = datetime.now().minute
            if curr_time - prev_time < 1:
                time.sleep((curr_time - prev_time) * 60)

        retry = 0
        while retry < 3:
            try:
                response = client.chat.completions.create(
                    model=locals()['LLM_MODEL'],
                    messages=messages,
                    temperature=locals()['LLM_TEMPERATURE'],
                    timeout=locals()['LLM_REPLY_TIMEOUT']
                )
                logger.info(f"Tokens used — Completion: {response.usage.completion_tokens}, Prompt: {response.usage.prompt_tokens}, Total: {response.usage.total_tokens}")
                break
            except openai.APITimeoutError:
                logger.warning("LLM API Query Timed Out. Retrying......")
                retry += 1

            if retry == 3:
                logger.error("LLM API Query Timed Out. Exiting......")
                main_flag = False
                break

        epoch += 1
        response_text = response.choices[0].message.content
        logger.info(f"Epoch {epoch} Answer:\n{response_text}")
        epoch_prompt = Epoch_message.format(epoch=epoch)

        # Extract and execute action
        action, action_input = aci.extract_action_and_input(response_text)
        logger.info(f"Action: {action}\nInput: {action_input}")

        
        if action == "Use_Command":
            response_format_error_flag = False
            observation, exit_code = aci.run_command_with_timeout(aci.container, action_input.strip(), aci.config.get('env_variables')["COMMAND_TIMEOUT"])
            if exit_code == "0":
                content = f"Observation: Your command ran successfully with exit code {exit_code}.\n{observation}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})\nbash-$" + epoch_prompt + Self_critic_message
                history_processor.extend_msg(messages, response_text, content)
            else:
                content = f"Observation: Your command failed with exit code {exit_code}.\n{observation}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})\nbash-$" + epoch_prompt + Self_critic_message
                history_processor.extend_msg(messages, response_text, content)
        elif action == "Analyze_Target":
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 5, update=False)
            content = f"Target Analysis Output:\n{observation}\n{epoch_prompt}"
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Obeservate_Terminal":
            response_format_error_flag = False
            observation = aci.observate_terminal()
            content = f"Observation: {observation}\n(Open file: {aci.open_file})\n(Current directory: {aci.working_dir})\nbash-$" + epoch_prompt + Self_critic_message
            history_processor.extend_msg(messages, response_text, content)
            
        elif action == "Generate_Harness":
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 10, update=False)
            content = f"Harness Generated:\n{observation}\n{epoch_prompt}"
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Compile_Harness":
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 10, update=False)
            content = f"Compilation Output:\n{observation}\n{epoch_prompt}"
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Test_Harness":
            observation = aci.run_command_non_blocking(aci.container, action_input.strip(), 5, update=False)
            content = f"Test Result:\n{observation}\n{epoch_prompt}"
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Respond_to_Human":
            logger.info(f"Final Result: {action_input}")
            output_file = locals()['harness_generator_output_file']
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
            logger.error("Unrecognized or failed action.")
            if not response_format_error_flag:
                history_processor.record_history(messages)
            response_format_error_flag = True
            content = Error_message.format(open_file=aci.open_file, working_dir=aci.working_dir) + epoch_prompt + Self_critic_message
            history_processor.extend_msg(messages, response_text, content)

    aci.kill_process_tree(aci.container.pid)
    aci.container.terminate()
