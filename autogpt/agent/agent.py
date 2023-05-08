from colorama import Fore, Style

from autogpt.app import execute_command, get_command, get_commands, cmd_response_needs_verification, parse_cmd_response
from autogpt.config import Config
from autogpt.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from autogpt.json_utils.utilities import LLM_DEFAULT_RESPONSE_FORMAT, validate_json
from autogpt.llm import chat_with_ai, create_chat_completion, create_chat_message, call_ai_function
from autogpt.llm.token_counter import count_string_tokens
from autogpt.logs import logger, print_assistant_thoughts, print_assistant_commands
from autogpt.speech import say_text
from autogpt.spinner import Spinner
from autogpt.utils import clean_input
from autogpt.workspace import Workspace

from autogpt.commands.file_operations import read_file

class Agent:
    """Agent class for interacting with Auto-GPT.

    Attributes:
        ai_name: The name of the agent.
        memory: The memory object to use.
        full_message_history: The full message history.
        next_action_count: The number of actions to execute.
        system_prompt: The system prompt is the initial prompt that defines everything
          the AI needs to know to achieve its task successfully.
        Currently, the dynamic and customizable information in the system prompt are
          ai_name, description and goals.

        triggering_prompt: The last sentence the AI will see before answering.
            For Auto-GPT, this prompt is:
            Determine which next command to use, and respond using the format specified
              above:
            The triggering prompt is not part of the system prompt because between the
              system prompt and the triggering
            prompt we have contextual information that can distract the AI and make it
              forget that its goal is to find the next task to achieve.
            SYSTEM PROMPT
            CONTEXTUAL INFORMATION (memory, previous conversations, anything relevant)
            TRIGGERING PROMPT

        The triggering prompt reminds the AI about its short term meta task
        (defining the next task)
    """

    def __init__(
        self,
        ai_name,
        memory,
        full_message_history,
        next_action_count,
        command_registry,
        config,
        system_prompt,
        triggering_prompt,
        workspace_directory,
    ):
        cfg = Config()
        self.ai_name = ai_name
        self.memory = memory
        self.summary_memory = (
            "I was created."  # Initial memory necessary to avoid hilucination
        )
        self.last_memory_index = 0
        self.full_message_history = full_message_history
        self.next_action_count = next_action_count
        self.command_registry = command_registry
        self.config = config
        self.system_prompt = system_prompt
        self.triggering_prompt = triggering_prompt
        self.workspace_directory = workspace_directory
        self.workspace = Workspace(workspace_directory, cfg.restrict_to_workspace)

    def start_interaction_loop(self):
        # Interaction Loop
        cfg = Config()
        loop_count = 0
        command_name = None
        arguments = None
        user_input = ""

        while True:
            # Discontinue if continuous limit is reached
            loop_count += 1
            if (
                cfg.continuous_mode
                and cfg.continuous_limit > 0
                and loop_count > cfg.continuous_limit
            ):
                logger.typewriter_log(
                    "Continuous Limit Reached: ", Fore.YELLOW, f"{cfg.continuous_limit}"
                )
                break
            # Send message to AI, get response
            with Spinner("Thinking... "):
                assistant_reply = chat_with_ai(
                    self,
                    self.system_prompt,
                    self.triggering_prompt,
                    self.full_message_history,
                    self.memory,
                    cfg.smart_token_limit,
                )  # TODO: This hardcodes the model to use GPT3.5. Make this an argument

            assistant_reply_json = fix_json_using_multiple_techniques(assistant_reply)
            for plugin in cfg.plugins:
                if not plugin.can_handle_post_planning():
                    continue
                assistant_reply_json = plugin.post_planning(self, assistant_reply_json)

            if assistant_reply_json == None:
                logger.typewriter_log("Failed to parse the response from the AI.")
                self.user_input = "NOT GOOD: INVALID JSON. GENERATE A VALID JSON RESPONSE."
                self.full_message_history.append(
                    create_chat_message("system", self.user_input)
                )
                continue

            commands = []

            # Print Assistant thoughts
            if assistant_reply_json != {}:
                validate_json(assistant_reply_json, LLM_DEFAULT_RESPONSE_FORMAT)
                # Get command name and arguments
                try:
                    print_assistant_thoughts(
                        self.ai_name, assistant_reply_json, cfg.speak_mode
                    )
                    print_assistant_commands(self.ai_name, assistant_reply_json)
                    # command_name, arguments = get_command(assistant_reply_json)
                    commands = get_commands(
                        assistant_reply_json
                    )
                except Exception as e:
                    logger.error("Error: \n", str(e))

            # avoid too many values to unpack (expected 2) error
            if commands is None or len(commands) == 0 or len(commands[0]) != 3:
                logger.typewriter_log("No commands found in response.")
                self.user_input = "NOT GOOD: THE \"commands\" LIST IS EMPTY. GENERATE A JSON RESPONSE WITH COMMANDS."
                self.full_message_history.append(
                    create_chat_message("system", self.user_input)
                )
                continue

            # Execute commands
            last_command_response = ""
            command_results = []

            for cmd_index, command in enumerate(commands):
                command_name = command.get("name")
                arguments = command.get("args")
                logger.debug(f"Executing command {command_name} {cmd_index + 1} out of {len(commands)}")

                if cfg.speak_mode:
                    say_text(f"I want to execute {command_name}")

                arguments = self._resolve_pathlike_command_args(arguments)

                if not cfg.continuous_mode and self.next_action_count == 0:
                    # ### GET USER AUTHORIZATION TO EXECUTE COMMAND ###
                    # Get key press: Prompt the user to press enter to continue or escape
                    # to exit
                    self.user_input = ""
                    logger.typewriter_log(
                        "NEXT ACTION: ",
                        Fore.CYAN,
                        f"COMMAND = {Fore.CYAN}{command_name}{Style.RESET_ALL}  "
                        f"ARGUMENTS = {Fore.CYAN}{arguments}{Style.RESET_ALL}",
                    )

                    logger.info(
                        "Enter 'y' to authorise command, 'y -N' to run N continuous commands, 's' to run self-feedback commands"
                        "'n' to exit program, or enter feedback for "
                        f"{self.ai_name}..."
                    )

                    while True:
                        if cfg.chat_messages_enabled:
                            console_input = clean_input("Waiting for your response...")
                        else:
                            console_input = clean_input(
                                Fore.MAGENTA + "Input:" + Style.RESET_ALL
                            )
                        if console_input.lower().strip() == cfg.authorise_key:
                            user_input = "GENERATE NEXT JSON RESPONSE"
                            break
                        elif console_input.lower().strip() == "s":
                            logger.typewriter_log(
                                "-=-=-=-=-=-=-= THOUGHTS, REASONING, PLAN AND CRITICISM WILL NOW BE VERIFIED BY AGENT -=-=-=-=-=-=-=",
                                Fore.GREEN,
                                "",
                            )
                            thoughts = assistant_reply_json.get("thoughts", {})
                            self_feedback_resp = self.get_self_feedback(
                                thoughts, cfg.fast_llm_model
                            )
                            logger.typewriter_log(
                                f"SELF FEEDBACK: {self_feedback_resp}",
                                Fore.YELLOW,
                                "",
                            )
                            if self_feedback_resp[0].lower().strip() == cfg.authorise_key:
                                user_input = "GENERATE NEXT JSON RESPONSE"
                            else:
                                user_input = self_feedback_resp
                            break
                        elif console_input.lower().strip() == "":
                            logger.warn("Invalid input format.")
                            continue
                        elif console_input.lower().startswith(f"{cfg.authorise_key} -"):
                            try:
                                self.next_action_count = abs(
                                    int(console_input.split(" ")[1])
                                )
                                user_input = "GENERATE NEXT JSON RESPONSE"
                            except ValueError:
                                logger.warn(
                                    "Invalid input format. Please enter 'y -n' where n is"
                                    " the number of continuous tasks."
                                )
                                continue
                            break
                        elif console_input.lower() == cfg.exit_key:
                            user_input = "EXIT"
                            break
                        else:
                            user_input = console_input
                            command_name = "human_feedback"
                            break

                    if user_input == "GENERATE NEXT JSON RESPONSE":
                        logger.typewriter_log(
                            "-=-=-=-=-=-=-= COMMAND AUTHORISED BY USER -=-=-=-=-=-=-=",
                            Fore.MAGENTA,
                            "",
                        )
                    elif user_input == "EXIT":
                        logger.info("Exiting...")
                        break
                else:
                    # Print command
                    logger.typewriter_log(
                        "NEXT ACTION: ",
                        Fore.CYAN,
                        f"COMMAND = {Fore.CYAN}{command_name}{Style.RESET_ALL}"
                        f"  ARGUMENTS = {Fore.CYAN}{arguments}{Style.RESET_ALL}",
                    )

                # Execute command
                command_successful = False
                last_command_response = ""
                if command_name is not None and command_name.lower().startswith("error"):
                    result = (
                        f"Command {command_name} threw the following error: {arguments}"
                    )
                elif command_name == "human_feedback":
                    result = f"Human feedback: {user_input}"
                elif command_name == "send_final_response":
                    return arguments.get("response")
                elif command_name == "check_task_completion":
                    return self.check_task_completion()
                elif command_name == "abort":
                    return f"Aborting. Reason: {arguments.get('reason')}"
                else:
                    for plugin in cfg.plugins:
                        if not plugin.can_handle_pre_command():
                            continue
                        command_name, arguments = plugin.pre_command(
                            command_name, arguments
                        )
                    command_result = self.execute_main_command(
                        command_name,
                        arguments
                    )
                    result = f"Command {command_name} returned: " f"{command_result}"

                    result_tlength = count_string_tokens(
                        str(command_result), cfg.fast_llm_model
                    )
                    memory_tlength = count_string_tokens(
                        str(self.summary_memory), cfg.fast_llm_model
                    )
                    # TODO: check if 600 is a good number for a multi-command plan
                    if result_tlength + memory_tlength + 600 > cfg.fast_token_limit:
                        command_successful = False
                        result = f"Failure: command {command_name} returned too much output. \
                            Do not execute this command again with the same arguments."

                    for plugin in cfg.plugins:
                        if not plugin.can_handle_post_command():
                            continue
                        result = plugin.post_command(command_name, result)
                    if self.next_action_count > 0:
                        self.next_action_count -= 1

                    # Check if the command was successful
                    if cmd_response_needs_verification(command_name):
                        command_successful = parse_cmd_response(command_name, arguments, command_result)
                    elif "Unknown command" in result: # TODO: check the result for unknown commands after 0.3.0 update
                        command_successful = False
                    else:
                        command_successful = True

                    if command_successful:
                        last_command_response = result
                        logger.typewriter_log(
                            "COMMAND EXECUTION SUCCESS", Fore.GREEN, ""
                        )
                        self.user_input = "ALL COMMANDS EXECUTED!"
                    else:
                        logger.typewriter_log(
                            "COMMAND EXECUTION FAILURE", Fore.RED, ""
                        )
                        self.user_input = f"THE {command_name} COMMAND FAILED, ABORTING PLAN."

                # Check if there's a result from the command append it to the message
                # history
                if result is not None:
                    self.full_message_history.append(create_chat_message("system", result))
                    logger.typewriter_log("SYSTEM: ", Fore.YELLOW, result)
                else:
                    self.full_message_history.append(
                        create_chat_message("system", "Unable to execute command")
                    )
                    logger.typewriter_log(
                        "SYSTEM: ", Fore.YELLOW, "Unable to execute command"
                    )


                if not command_successful:
                    break

            self.full_message_history.append(create_chat_message("system", self.user_input))
            memory_to_add = (
                f"Assistant Reply: {assistant_reply} "
                f"\nResult: {result} "
                f"\nHuman Feedback: {user_input} "
            )
            self.memory.add(memory_to_add)

    def execute_main_command(self, command_name: str, arguments: dict):
        """Executes a command and returns the result."""
        if command_name == "start_sub_agent":
            name = arguments.get("name")
            role = arguments.get("role")
            goal = arguments.get("goal")
            respond_with = arguments.get("respond_with")
            start_memory = arguments.get("data") or None
            return self.start_sub_agent(
                name,
                role,
                [goal, f"You must respond with {respond_with}"],
                start_memory
            )
        else:
            return execute_command(self.command_registry, command_name, arguments, self.config.prompt_generator)

    def start_sub_agent(
        self,
        ai_name,
        ai_role,
        ai_goals,
        start_memory) -> None:
        """Starts a sub-agent along with its iteraction loop."""

        from autogpt.memory import get_memory
        from autogpt.prompts.prompt_sub_agent import build_sub_agent_prompt_generator, construct_sub_agent_ai_config

        cfg = Config()
        prompt_generator = build_sub_agent_prompt_generator()
        # Initialize variables
        full_message_history = []
        if start_memory is not None and start_memory != "":
            full_message_history.append(create_chat_message("user", f"Context: {start_memory}"))
        next_action_count = 0

        # Initialize memory and make sure it is empty.
        # this is particularly important for indexing and referencing pinecone memory
        memory = get_memory(cfg, init=True)
        logger.typewriter_log(
            "Using memory of type:", Fore.GREEN, f"{memory.__class__.__name__}"
        )
        logger.typewriter_log("Using Browser:", Fore.GREEN, cfg.selenium_web_browser)

        ai_config = construct_sub_agent_ai_config(ai_name, ai_role, ai_goals)
        sub_prompt = ai_config.construct_full_prompt(prompt_generator)
        if cfg.debug_mode:
            logger.typewriter_log("Prompt:", Fore.GREEN, sub_prompt)

        sub_agent = Agent(
            ai_name=ai_name,
            memory=memory,
            full_message_history=full_message_history,
            next_action_count=next_action_count,
            command_registry=self.command_registry,
            config=self.config,
            system_prompt=sub_prompt,
            triggering_prompt=self.triggering_prompt,
            workspace_directory=self.workspace_directory
        )
        return sub_agent.start_interaction_loop()

    def check_task_completion(self) -> str:
        """Message an agent with a given key and message"""

        content = read_file(f"{self.workspace_directory}/recipes.html")

        logger.info(f"Content: {content}")

        prompt = f"Are there two complete recipes (ingredients and instructions) in the following content?\n\n{content} Reply with \"Yes\" or \"No\" + what is missing."
        return create_chat_completion(
            model=CFG.smart_llm_model,
            messages=[{"role": "system", "content": "you are a smart assistant"}, {"role": "user", "content": prompt}],
            max_tokens=8000,
        )

    def replace_arguments(self, command:str, arguments:str, last_command_response:str) -> dict:
        """Replace the arguments in the command based on the previous command response."""

        fixed_arguments_json = {}
        try:
            logger.debug("------------ Argument Replacement ---------------")
            logger.debug(f"Command: {command}")
            logger.debug(f"Template Arguments: {arguments}")
            logger.debug(f"Last Command Response: {last_command_response}")
            logger.debug("-----------")

            # return arguments if no argument value is within <some text>
            found = False
            for (i, arg) in enumerate(arguments):
                if "<" in arg:
                    found = True
                    break
            if not found:
                logger.debug(f"Arguments: {arguments}")
                logger.debug("----------- End of Argument Replacement ----------------")
                return arguments

            # replace the <arg value> placeholders in the arguments with the appropriate values
            function_string = "def replace_arguments(command:str, arguments:str, last_command_response:str) -> str:"
            args = [f"'''{command}'''", f"'''{arguments}'''", f"'''{last_command_response}'''"]
            description_string = (
                "Given a command and its arguments (if any) formatted as JSON,"
                "and the response from the last command,"
                "replace <argument> occurences within arguments with the corresponding values from the last_command_response."
                "Returns the new arguments as a parsable JSON string.\n"
                "This is used to determine the arguments for the current command based on the previous command response."
            )
            result_string = call_ai_function(
                function_string, args, description_string, model=cfg.fast_llm_model
            )
            result_string = result_string.replace("'''", "")
            logger.debug(f"Arguments: {result_string}")
            logger.debug("----------- End of Argument Replacement ----------------")

            fixed_arguments_json = json.loads(result_string)

        except (json.JSONDecodeError, ValueError) as e:
            if cfg.debug_mode:
                logger.error(f"Error: Invalid JSON arguments: %s\n", result_string)
            logger.error("Error: Failed to replace JSON arguments.\n")
            fixed_arguments_json = None

        return fixed_arguments_json


    def _resolve_pathlike_command_args(self, command_args):
        if "directory" in command_args and command_args["directory"] in {"", "/"}:
            command_args["directory"] = str(self.workspace.root)
        else:
            for pathlike in ["filename", "directory", "clone_path"]:
                if pathlike in command_args:
                    command_args[pathlike] = str(
                        self.workspace.get_path(command_args[pathlike])
                    )
        return command_args

    def get_self_feedback(self, thoughts: dict, llm_model: str) -> str:
        """Generates a feedback response based on the provided thoughts dictionary.
        This method takes in a dictionary of thoughts containing keys such as 'reasoning',
        'plan', 'thoughts', and 'criticism'. It combines these elements into a single
        feedback message and uses the create_chat_completion() function to generate a
        response based on the input message.
        Args:
            thoughts (dict): A dictionary containing thought elements like reasoning,
            plan, thoughts, and criticism.
        Returns:
            str: A feedback response generated using the provided thoughts dictionary.
        """
        ai_role = self.config.ai_role

        feedback_prompt = f"Below is a message from an AI agent with the role of {ai_role}. Please review the provided Thought, Reasoning, Plan, and Criticism. If these elements accurately contribute to the successful execution of the assumed role, respond with the letter 'Y' followed by a space, and then explain why it is effective. If the provided information is not suitable for achieving the role's objectives, please provide one or more sentences addressing the issue and suggesting a resolution."
        reasoning = thoughts.get("reasoning", "")
        plan = thoughts.get("plan", "")
        thought = thoughts.get("thoughts", "")
        criticism = thoughts.get("criticism", "")
        feedback_thoughts = thought + reasoning + plan + criticism
        return create_chat_completion(
            [{"role": "user", "content": feedback_prompt + feedback_thoughts}],
            llm_model,
        )
