from agents.builder.agent import run_builder
from agents.seeds_generator.agent import run_seed_generator
from agents.dictionary.agent import run_dictionary_generator
from agents.harness_generator.agent import run_harness_generator
from agents.fuzzer_executer.agent import run_executer
from agents.crash_analyzer.agent import run_crash_analyzer
import os
import openai
from openai import OpenAI
from utils.aci import *
from utils.log import *
from planning.history_processor import HistoryProcessor
from planning.prompt import *
from agents.manager.prompt import *



def run_manager_agent(input_msg: str = None):
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

    summaries = {}  # <- store agent summaries here

    # Mapping agent names to their runner functions
    agent_map = {
        "builder": run_builder,
        "seed_generator": run_seed_generator,
        "dictionary": run_dictionary_generator,
        "harness": run_harness_generator,
        "executor": run_executer,
        "crash_analyzer": run_crash_analyzer,
    }
    
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

        if action == "Collect_Summary":
            response_format_error_flag = False
            all_summaries = "\n\n".join([f"### {k.upper()} AGENT ###\n{v}" for k, v in summaries.items()])
            content = f"Collected all summaries:\n{all_summaries or '(no summaries yet)'}\n{epoch_prompt}"
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Analyze_Summary":
            response_format_error_flag = False
            content = "Analyzing summaries and deciding next step...\n" + epoch_prompt
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Run_Agent":
            response_format_error_flag = False
            agent_key = action_input.strip()
            if agent_key not in agent_map:
                logger.warning(f"Unknown agent: {agent_key}")
                content = f"Unknown agent `{agent_key}`.\n{epoch_prompt}"
                history_processor.extend_msg(messages, response_text, content)
                continue
            logger.info(f"Running agent `{agent_key}`")
            summary = agent_map[agent_key]()  
            summaries[agent_key] = summary
            content = f"Agent `{agent_key}` finished.\nSummary:\n{summary}\n{epoch_prompt}"
            history_processor.extend_msg(messages, response_text, content)

        elif action == "Respond_to_Human":
            logger.info(f"Final Result: {action_input}")
            output_file = locals()['manager_output_file']
            with open(output_file, 'w') as f:
                f.write(action_input)
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
