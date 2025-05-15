# SimpleLLMFuzzer
An Automatic LLM-driven Fuzzer
FuzzAgent is an autonomous fuzzing test agents for real-world projects.

## Project Structure
* `agents`: The fuzzing agents in different roles.
* `docker`: Files for building the docker image.
* `planning`: The common module makes the planning for all agents.
* `tools`: The tools used in the agents.
* `utils`: The common used sub-modules and utilities used in the project.
* `working_dir`: The working directory to store target projects.
* `run.py`: The entry script to run the agents.
* `config.yaml`: The configuration file for the project.
* `.env_template`: The template of environment variables settings for the project.
* `requirements.txt`: The requirements for the project.
* `LICENSE`: The license of the project.
* `README.md`: The readme file for the project.



## Usage
The project is built and tested on Ubuntu 24.04.1 LTS with docker.
Now only the builder agent is available.

### System configuration
Set system core dumps as AFL (on the host if you execute Hopper in a Docker container).

``` bash
sudo echo core | sudo tee /proc/sys/kernel/core_pattern
```


### Download Target Project
Take the target project from the official website and put it in the `working_dir` directory.
```bash
cd working_dir
# Take jhead as the example
git clone https://github.com/Matthias-Wandel/jhead.git
```

### Environment

Create the `.env` file from `.env_template` in the `SimpleFuzzAgent` directory.

You should  and set the `WORKING_DIR` to the path of the target project in the docker container.
``` text
# LLM API configurations
export OPENAI_API_BASE = "xxx" 
export OPENAI_API_KEY = "sk-xxx"


# Runtime environment variables
export CONFIG_FILE = "/home/FuzzAgent/config.yaml"
export WORKING_DIR = "/home/FuzzAgent/working_dir/jhead"
export PROJECT_DIR = "/home/FuzzAgent"
```

### Docker

- Build the docker image:
```bash
cd SimpleFuzzAgent
docker build -t fuzzagent -f docker/Dockerfile .
```

 - Run the docker container:
``` bash
docker run -it --rm --name fuzzagent -v $(pwd):/home/FuzzAgent -w /home/FuzzAgent --network host fuzzagent /bin/bash
```


## How to Run
``` bash
python run.py
```
The running log will be written to the `run_{agent_name}_{prject_name}.log` file in the `WORKING_DIR/logs` directory.

Now the builder agent will build the target project itself and generate an exectuable file named the same as the project directory in the project root directory.
