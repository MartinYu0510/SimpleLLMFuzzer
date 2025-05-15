from dotenv import load_dotenv
load_dotenv() # Load environment variables before importing other modules

from agents.builder.agent import *
from agents.crash_analyzer.agent import *
from agents.dictionary.agent import *
from agents.fuzzer_executer.agent import *
from agents.harness_generator.agent import *
from agents.manager.agent import *
from agents.seeds_generator.agent import *

if __name__ == "__main__":
    # Builder Test
    run_builder()
    
    # Harness Generator Test
    run_harness_generator()
    
    # Seed Generator Test
    run_seed_generator()
    
    # Dictionary Generator Test
    run_dictionary_generator()
    
    
    
    # Fuzzer Executer Test
    run_executer()
    
    # Crash Analyzer Test
    run_crash_analyzer()
    
    # Manager Test
    # run_manager_agent()