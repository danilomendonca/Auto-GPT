from colorama import Fore

from autogpt.config import Config
from autogpt.config.ai_config import AIConfig
from autogpt.config.config import Config
from autogpt.logs import logger
from autogpt.promptgenerator import PromptGenerator
from autogpt.setup import prompt_user
from autogpt.utils import clean_input

CFG = Config()


def get_prompt() -> str:
    """
    This function generates a prompt string that includes various constraints,
        commands, resources, and performance evaluations.

    Returns:
        str: The generated prompt string.
    """

    # Initialize the Config object
    cfg = Config()

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
    prompt_generator.add_constraint(
        "Use subprocesses for commands that will not terminate within a few minutes"
    )

    # Improvements
    prompt_generator.add_constraint(
        'Sub-agents have no accesss to local files or folders'
    )
    prompt_generator.add_constraint(
        'Sub-agents have no accesss to google or internet browsing'
    )
    prompt_generator.add_constraint(
        'Do not include commands whose argument values depend on the output of other commands in the commands list'
    )
    prompt_generator.add_constraint(
        'Do not include //comments into the JSON response'
    )
    # Sub-agents
    prompt_generator.add_constraint(
        'Sub-agents have no memory of previous conversations. Send any relevant information in the "input" field.'
    )
    prompt_generator.add_constraint(
        'Be specific with sub-agent goals. Specify what they should respond with.'
    )
    #prompt_generator.add_constraint(
    #    'Always include at least one command in the "commands" list'
    #)
    #prompt_generator.add_constraint(
    #    'Command arguments must be in valid JSON format e.g. {"arg_name": "arg_value"}'
    #)
    #prompt_generator.add_constraint(
    #    'Use the listed commands as self-sufficient subroutines'
    #)
    #prompt_generator.add_constraint(
    #    'Do not include commands whose arguments depend on the output of other commands in the commands list'
    #)
    #prompt_generator.add_constraint(
    #    'Use <angle brackets> to denote a replaceable text variable e.g. "<variable_name>".'
    #)

    # Define the command list
    commands = [
        #("Google Search", "google", {"input": "<search>"}),
        #(
        #    "Start GPT Agent",
        #    "start_agent",
        #    {"name": "<name>", "task": "<short_task_desc>", "prompt": "<prompt>"},
        #),
        (
            "Start Sub-Agent",
            "start_sub_agent",
            {"name": "<name>", "role": "<role>", "goal": "<short_goal_desc>", "input": "<context or input needed for goal>", "respond_with": "<the sub agent final response specification>"},
        ),
        #("List GPT Agents", "list_agents", {}),
        #(
        #    "Ask existing Sub-Agent",
        #    "ask_agent",
        #    {"key": "<key>", "prompt": "<prompt>"},
        #),
        #(
        #    "Browse Website",
        #    "browse_website",
        #    {"url": "<url>", "question": "<what_you_want_to_find_on_website>"},
        #),
        #("Save to memory", "save_to_mem", {"key": "<key>", "value": "<value>"}),
        #("Load from memory", "load_from_mem", {"key": "<key>"}),
        #("Delete GPT Agent", "delete_agent", {"key": "<key>"}),
        ("Create file", "create_file", {"file": "<file>"}),
        #(
        #    "Clone Repository",
        #    "clone_repository",
        #    {"repository_url": "<url>", "clone_path": "<directory>"},
        #),
        #("Write to file", "write_to_file", {"file": "<file>", "text": "<text>"}),
        ("Read file", "read_file", {"file": "<file>"}),
        ("Delete file", "delete_file", {"file": "<file>"}),
        #("File exists", "file_exists", {"file": "<file>"}),
        ("Append to file", "append_to_file", {"file": "<file>", "text": "<text>"}),
        ("Replace text in file", "replace_in_file", {"file": "<file>", "text": "<non empty text>", "new_text": "<new_text>"}),
        ("Search Files", "search_files", {"directory": "<directory>"}),
        #("Analyze Code", "analyze_code", {"code": "<full_code_string>"}),
        #(
        #    "Get Improved Code",
        #    "improve_code",
        #    {"suggestions": "<list_of_suggestions>", "code": "<full_code_string>"},
        #),
        #(
        #    "Write Tests",
        #    "write_tests",
        #    {"code": "<full_code_string>", "focus": "<list_of_focus_areas>"},
        #),
        #("Execute Python File", "execute_python_file", {"file": "<file>"}),
        ("Generate Image", "generate_image", {"prompt": "<detailed image prompt>"}),
        #("Send Tweet", "send_tweet", {"text": "<text>"}),
    ]

    # Only add the audio to text command if the model is specified
    if cfg.huggingface_audio_to_text_model:
        commands.append(
            ("Convert Audio to text", "read_audio_from_file", {"file": "<file>"}),
        )

    # Only add shell command to the prompt if the AI is allowed to execute it
    if cfg.execute_local_commands:
        commands.append(
            (
                "Execute Shell Command, non-interactive commands only",
                "execute_shell",
                {"command_line": "<command_line>"},
            ),
        )
        commands.append(
            (
                "Execute Shell Command Popen, non-interactive commands only",
                "execute_shell_popen",
                {"command_line": "<command_line>"},
            ),
        )

    # Only add the download file command if the AI is allowed to execute it
    if cfg.allow_downloads:
        commands.append(
            (
                "Downloads a file from the internet, and stores it locally",
                "download_file",
                {"url": "<file_url>", "file": "<saved_filename>"},
            ),
        )

    # Add these command last.
    #commands.append(
    #    ("Do Nothing", "do_nothing", {}),
    #)
    commands.append(
        ("Task Complete (Shutdown)", "task_complete", {"reason": "<reason>"}),
    )

    # Add commands to the PromptGenerator object
    for command_label, command_name, args in commands:
        prompt_generator.add_command(command_label, command_name, args)

    # Add resources to the PromptGenerator object
    prompt_generator.add_resource(
        "Internet access for searches and information gathering."
    )
    prompt_generator.add_resource("Long Term memory management.")
    #prompt_generator.add_resource(
    #    "GPT-3.5 powered Agents for delegation of simple tasks."
    #)
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

    # Generate the prompt string
    return prompt_generator.generate_prompt_string()


def construct_prompt() -> str:
    """Construct the prompt for the AI to respond to

    Returns:
        str: The prompt string
    """
    config = AIConfig.load(CFG.ai_settings_file)
    if CFG.skip_reprompt and config.ai_name:
        logger.typewriter_log("Name :", Fore.GREEN, config.ai_name)
        logger.typewriter_log("Role :", Fore.GREEN, config.ai_role)
        logger.typewriter_log("Goals:", Fore.GREEN, f"{config.ai_goals}")
    elif config.ai_name:
        logger.typewriter_log(
            "Welcome back! ",
            Fore.GREEN,
            f"Would you like me to return to being {config.ai_name}?",
            speak_text=True,
        )
        should_continue = clean_input(
            f"""Continue with the last settings?
Name:  {config.ai_name}
Role:  {config.ai_role}
Goals: {config.ai_goals}
Continue (y/n): """
        )
        if should_continue.lower() == "n":
            config = AIConfig()

    if not config.ai_name:
        config = prompt_user()
        config.save(CFG.ai_settings_file)

    # Get rid of this global:
    global ai_name
    ai_name = config.ai_name

    return config.construct_full_prompt()
