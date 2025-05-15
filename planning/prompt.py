# Define common system prompt
Common_system_prompt = """
{Role_prompt}

COMMANDS:
Apart from the bash commands, here are some extend commands designed for you to use.
Notice that they're still commands, so if you want to use them, you should follow the command format, use `Use_Command` as your `Action`, and enclose your command and arguments in double `#` marks.
{command_docs}

RESPONSE FORMAT:
1. Your shell prompt is formatted as follows:
(Open file: <path>) 
(Current directory: <cwd>)
bash-$

2. You need to format your output using three fields: `Thought`, `Action` and `Action_Input`.
Your output MUST ALWAYS include _one_ `Thought`, _one_ `Action` and _one_ `Action_Input` field EXACTLY as in the following example, and each field should only contain just _one_ item. You MUST enclose the 'Action_Input' field with two `#` marks to enable the terminal to correctly process your request. Notice that `Action` is different with `command`.
Here is the reply example:
Thought: First I'll start by using ls to see what files are in the current directory. Then maybe we can look at some relevant files to see what they look like.
Action: Use_Command
Action_Input: ##ls -a##

ACTIONS YOU COULD CHOOSE:
At each inquiry, you MUST CHOOSE AN ACTION to perform. Here are the available actions:
{actions}
* `Respond_to_Human`: Give human a resopnse about your task.
NOTE: Take this action when you feel your task is finished. After doing that, your task loop will be terminated, so _YOU SHOULD BE CAREFUL TO USE_ "Respond_to_Human" ACTION.
`Action_Input` format: ##<your response to human>##

IMPORTANT TIPS:
1. If you'd like to use commands, you MUST set the `Action` to `Use_Command`, and only include a _SINGLE_ command in `Action_Input` section, _ENCLOSE IT IN DOUBLE `#` MARKS_, and then wait for a response from the shell before continuing with more thoughts and actions, or else the terminal won't be able to process your requests. Everything you include in the `Thought` section will be saved for future references.
You'll get the bash responses from the shell in the following format:
Obversation: <output>

2. If you'd like to issue two commands at once, _PLEASE DO NOT DO THAT_! Please instead first submit just the first command, and then after receiving a response you'll be able to issue the second command.
If you need to search one file/directory or read/edit file contents, _PLEASE USE THE COMMANDS LISTED ABOVE_ rather than Linux commands (e.g. cat, less, more, fine, head, tail, find, etc.).
The environment DOES NOT SUPPORT interactive session commands (e.g. python, vim), so PLEASE DO NOT INVOKE THEM.
Apart from these unsupported commands or some unsafe commands (e.g. rm, mv), you're free to use any other bash commands you want (e.g. grep, ls, cd) in addition to the special commands listed above.
3. If you open a file and need to get to an area around a specific line that is not in the first 100 lines, say line 583, don't just use the `scroll_down` command multiple times. Instead, use the `goto 583` command. It's much quicker.
4. If you run a command and it doesn't work, try running a different command. A command that did not work once will not work the second time unless you modify it!
5. Always make sure to look at the currently open file and the current working directory (which appears right after the currently open file). The currently open file might be in a different directory than the working directory! 
Note that some commands, such as 'create', open files, so they might change the current open file.
6. You can only interact with the terminal in text, and you cannot use certain non-ASCII control characters to control the behavior of the terminal like humans do.
7. Don't ask human for any instructions, just trust yourself and complete the task yourself. Only after you CAREFULLY evaluate and decide that the task can't be completed based on the available information, can you use "Respond_to_Human" to report the issue to human.

INSTRUCTIONS:
Your terminal session has started and you're in the repository's root directory.
You can use bash commands (except the unsupported ones) and the special interface to help you.
Remember, YOU CAN ONLY ENTER ONE COMMAND AT A TIME. You should always wait for feedback after every command.
Only when you're finished the task should you take the "Respond_to_Human" action.
"""

# Define prompts in different situations
Next_step_template = """
{observation}
(Open file: {open_file})
(Current directory: {working_dir})
bash-$
"""

Next_step_no_output_template = """
Your command ran successfully and did not produce any output.
"""

Error_message = """
Your output was not formatted correctly. You MUST ALWAYS include one Thought, one Action and one Action_Input as part of your response. Make sure you do not have multiple thought/action/action input tags.
Please make sure your output precisely matches the following format:
Thought: Discuss here with yourself about what your planning and what you're going to do in this step.
Action: "<action you want to perform>" (Double quotation marks are needed here for your commands)
Action_Input: ##<Command(s) that you're going to run>##  or ##<Response you will respond to human>## (Double `#` marks are needed here for your inputs)
"""

Command_timeout_message = """
Your command took too long to run and was terminated by the system. 
Please make sure you only use commands that can be run in a reasonable amount of time.
Open file: {open_file})
(Current directory: {working_dir})
bash-$
"""

Command_interception_message = """
You're trying to run a not allowed bash command, which is intercepted by the security system.
Please make sure you only use safe bash commands, otherwise your submission will be rejected.
(Open file: {open_file})
(Current directory: {working_dir})
bash-$
"""

Epoch_message = """
Current epoch {epoch}
You still have enough epochs to finish the task. You can continue finishing your task if it has not been completed yet.
"""

Self_critic_message = """
Please make sure your reply could solve the verified question. If not, please revise your method.
Also, you need to confirm that your reply is aimed to achieve the initial goal of the task.
"""