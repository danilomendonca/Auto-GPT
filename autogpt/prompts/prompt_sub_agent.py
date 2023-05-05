from colorama import Fore

from autogpt.config.ai_config import AIConfig
from autogpt.config.config import Config
from autogpt.llm import ApiManager
from autogpt.logs import logger
from autogpt.prompts.generator import PromptGenerator
from autogpt.setup import prompt_user
from autogpt.utils import clean_input

CFG = Config()

DEFAULT_TRIGGERING_PROMPT = (
    "Determine which next command to use, and respond using the format specified above:"
)


def build_sub_agent_prompt_generator() -> PromptGenerator:
    """
    This function generates a prompt string that includes various constraints,
        commands, resources, and performance evaluations.

    Returns:
        str: The generated prompt string.
    """

    # Initialize the PromptGenerator object
    prompt_generator = PromptGenerator()

    # Add constraints to the PromptGenerator object
    prompt_generator.add_constraint(
        "~4000 word limit for short term memory. Your short term memory is short, so"
        " immediately save important information to files."
    )
    prompt_generator.add_constraint(
        "If you are unsure how you previously did something or want to recall past"
        " events, thinking about similar events will help you remember."
    )
    prompt_generator.add_constraint("No user assistance")
    prompt_generator.add_constraint(
        'Exclusively use the commands listed in double quotes e.g. "command name"'
    )

    # Improvements
    ## Commands
    prompt_generator.add_constraint(
        'Do not include commands whose argument values depend on the output of other commands in the commands list'
    )
    prompt_generator.add_constraint(
        'Do not include //comments into the JSON response'
    )
    ## Sub-agents
    prompt_generator.add_constraint(
        'Include all relevant information in the final complete response once the goal has been achieved'
    )'Be specific with sub-agent goals. Specify what they should respond with.'

    # Define the command list
    commands = [
        ("Ask GPT-4", "ask_gpt4", {"prompt": "<prompt>"}),
        ("Task Complete (Shutdown)", "task_complete", {"reason": "<reason>"})
    ]

    blocked_commands = [
        "browse_website",
        "get_text_summary",
        "save_to_db",
        "load_from_db",
        "delete_agent",
        "create_file",
        "clone_path",
        "write_to_file",
        "read_file",
        "delete_file",
        "file_exists",
        "append_to_file",
        "replace_in_file",
        "search_files",
        "analyze_code",
        "code",
        "focus",
        "execute_python_file",
        "send_tweet"
    ]
    for command_name in blocked_commands:
        prompt_generator.add_to_block_list(command_name)

    # Add commands to the PromptGenerator object
    for command_label, command_name, args in commands:
        prompt_generator.add_command(command_label, command_name, args)

    # Add resources to the PromptGenerator object
    prompt_generator.add_resource(
        "Internet access for searches and information gathering."
    )
    prompt_generator.add_resource("Long Term memory management.")
    prompt_generator.add_resource(
        "GPT-3.5 powered Agents for delegation of simple tasks."
    )
    prompt_generator.add_resource("File output.")

    # Add performance evaluations to the PromptGenerator object
    prompt_generator.add_performance_evaluation(
        "Continuously review and analyze your actions to ensure you are performing to"
        " the best of your abilities."
    )
    prompt_generator.add_performance_evaluation(
        "Constructively self-criticize your big-picture behavior constantly."
    )
    prompt_generator.add_performance_evaluation(
        "Reflect on past decisions and strategies to refine your approach."
    )
    prompt_generator.add_performance_evaluation(
        "Every command has a cost, so be smart and efficient. Aim to complete tasks in"
        " the least number of steps."
    )
    prompt_generator.add_performance_evaluation("Write all code to a file.")
    return prompt_generator
