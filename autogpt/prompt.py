from autogpt.promptgenerator import PromptGenerator


def get_prompt() -> str:
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
    prompt_generator.add_constraint(
        'Command arguments must be in valid JSON format e.g. {"arg_name": "arg_value"}'
    )
    #prompt_generator.add_constraint(
    #    'Use the listed commands as self-sufficient subroutines'
    #)
    prompt_generator.add_constraint(
        'Always include at least one command in the commands list'
    )
    #prompt_generator.add_constraint(
    #    'Do not include commands whose arguments depend on the output of other commands in the commands list'
    #)
    #prompt_generator.add_constraint(
    #    'Use <angle brackets> to denote a replaceable text variable e.g. "<variable_name>".'
    #)

    # Define the command list
    commands = [
        ("Google Search", "google", {"input": "<search>"}),
        #(
        #    "Browse Website",
        #    "browse_website",
        #    {"url": "<url>", "question": "<what_you_want_to_find_on_website>"},
        #),
        (
            "Start GPT Agent",
            "start_agent",
            {"name": "<name>", "task": "<short_task_desc>", "prompt": "<prompt>"},
        ),
        (
            "Prompt GPT Agent",
            "prompt_agent",
            {"key": "<key>", "prompt": "<prompt>"},
        ),
        #("Save memory", "save_memory", {"key": "<key>", "value": "<value>"}),
        #("Load memory", "load_memory", {"key": "<key>"}),
        ("List GPT Agents", "list_agents", {}),
        ("Delete GPT Agent", "delete_agent", {"key": "<key>"}),
        #("Write to file", "write_to_file", {"file": "<file>", "text": "<text>"}),
        ("Create file", "create_file", {"file": "<file>"}),
        ("Read file", "read_file", {"file": "<file>"}),
        ("Delete file", "delete_file", {"file": "<file>"}),
        #("File exists", "file_exists", {"file": "<file>"}),
        ("Append to file", "append_to_file", {"file": "<file>", "text": "<text>"}),
        ("Replace text in file", "replace_in_file", {"file": "<file>", "text": "<text>", "new_text": "<new_text>"}),
        ("Search Files", "search_files", {"directory": "<directory>"}),
        #("Evaluate Code", "evaluate_code", {"code": "<full_code_string>"}),
        (
            "Get Improved Code",
            "improve_code",
            {"suggestions": "<list_of_suggestions>", "code": "<full_code_string>"},
        ),
        (
            "Write Tests",
            "write_tests",
            {"code": "<full_code_string>", "focus": "<list_of_focus_areas>"},
        ),
        #("Execute Python File", "execute_python_file", {"file": "<file>"}),
        #(
        #    "Execute Shell Command, non-interactive commands only",
        #    "execute_shell",
        #    {"command_line": "<command_line>"},
        #),
        ("Task Complete (Shutdown)", "task_complete", {"reason": "<reason>"}),
        ("Generate Image", "generate_image", {"prompt": "<prompt>"})#,
        #("Do Nothing", "do_nothing", {}),
    ]

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

    # Generate the prompt string
    return prompt_generator.generate_prompt_string()
