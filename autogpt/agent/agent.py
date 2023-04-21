from colorama import Fore, Style

from autogpt.app import execute_command, get_commands, cmd_response_needs_verification, parse_cmd_response
from autogpt.chat import chat_with_ai, create_chat_message
from autogpt.config import Config
from autogpt.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from autogpt.json_utils.utilities import validate_json
from autogpt.logs import logger, print_assistant_thoughts
from autogpt.speech import say_text
from autogpt.spinner import Spinner
from autogpt.utils import clean_input
from autogpt.llm_utils import call_ai_function

class Agent:
    """Agent class for interacting with Auto-GPT.

    Attributes:
        ai_name: The name of the agent.
        memory: The memory object to use.
        full_message_history: The full message history.
        next_action_count: The number of actions to execute.
        system_prompt: The system prompt is the initial prompt that defines everything the AI needs to know to achieve its task successfully.
        Currently, the dynamic and customizable information in the system prompt are ai_name, description and goals.

        triggering_prompt: The last sentence the AI will see before answering. For Auto-GPT, this prompt is:
            Determine which next command to use, and respond using the format specified above:
            The triggering prompt is not part of the system prompt because between the system prompt and the triggering
            prompt we have contextual information that can distract the AI and make it forget that its goal is to find the next task to achieve.
            SYSTEM PROMPT
            CONTEXTUAL INFORMATION (memory, previous conversations, anything relevant)
            TRIGGERING PROMPT

        The triggering prompt reminds the AI about its short term meta task (defining the next task)
    """

    def __init__(
        self,
        ai_name,
        memory,
        full_message_history,
        next_action_count,
        system_prompt,
        triggering_prompt,
    ):
        self.ai_name = ai_name
        self.memory = memory
        self.full_message_history = full_message_history
        self.next_action_count = next_action_count
        self.system_prompt = system_prompt
        self.triggering_prompt = triggering_prompt

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
                    self.system_prompt,
                    self.triggering_prompt,
                    self.full_message_history,
                    self.memory,
                    cfg.fast_token_limit,
                )  # TODO: This hardcodes the model to use GPT3.5. Make this an argument

            assistant_reply_json = fix_json_using_multiple_techniques(assistant_reply)

            commands = []

            # Print Assistant thoughts
            if assistant_reply_json != {}:
                validate_json(assistant_reply_json, "llm_response_format_1")
                # Get command name and arguments
                try:
                    print_assistant_thoughts(self.ai_name, assistant_reply_json)
                    # command_name, arguments = get_command(assistant_reply_json)
                    commands = get_commands(
                        assistant_reply
                    )
                    # command_name, arguments = assistant_reply_json_valid["command"]["name"], assistant_reply_json_valid["command"]["args"]
                    if cfg.speak_mode:
                        say_text(f"I want to execute {command_name}")
                except Exception as e:
                    logger.error("Error: \n", str(e))

            # avoid too many values to unpack (expected 2) error
            if commands is None or len(commands) == 0 or len(commands[0]) != 2:
                logger.typewriter_log("No commands found in response.")
                self.user_input = "NOT GOOD: THE \"commands\" LIST IS EMPTY. GENERATE A JSON RESPONSE WITH COMMANDS."
                continue

            # Execute commands
            last_command_response = ""

            for cmd_index, command in enumerate(commands):
                command_name = command.get("name")
                arguments = command.get("args")
                print(f"Executing command {command_name} {cmd_index + 1} out of {len(commands)}")

                if not cfg.continuous_mode and self.next_action_count == 0:
                    ### GET USER AUTHORIZATION TO EXECUTE COMMAND ###
                    # Get key press: Prompt the user to press enter to continue or escape
                    # to exit
                    logger.typewriter_log(
                        "NEXT ACTION: ",
                        Fore.CYAN,
                        f"COMMAND = {Fore.CYAN}{command_name}{Style.RESET_ALL}  "
                        f"ARGUMENTS = {Fore.CYAN}{arguments}{Style.RESET_ALL}",
                    )
                    print(
                        "Enter 'y' to authorise command, 'y -N' to run N continuous "
                        "commands, 'n' to exit program, or enter feedback for "
                        f"{self.ai_name}...",
                        flush=True,
                    )
                    while True:
                        console_input = clean_input(
                            Fore.MAGENTA + "Input:" + Style.RESET_ALL
                        )
                        if console_input.lower().strip() == "y":
                            user_input = "GENERATE NEXT JSON RESPONSE"
                            break
                        elif console_input.lower().strip() == "":
                            print("Invalid input format.")
                            continue
                        elif console_input.lower().startswith("y -"):
                            try:
                                self.next_action_count = abs(
                                    int(console_input.split(" ")[1])
                                )
                                user_input = "GENERATE NEXT JSON RESPONSE"
                            except ValueError:
                                print(
                                    "Invalid input format. Please enter 'y -n' where n is"
                                    " the number of continuous tasks."
                                )
                                continue
                            break
                        elif console_input.lower() == "n":
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
                        print("Exiting...", flush=True)
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
                    command_successful = True
                else:
                    result = (
                        f"Command {command_name} returned: "
                        f"{execute_command(command_name, arguments)}"
                    )
                    if self.next_action_count > 0:
                        self.next_action_count -= 1

                    if cmd_response_needs_verification(command_name):
                        command_successful = parse_cmd_response(command_name, arguments, result)
                    elif "Unknown command" in result:
                        command_successful = False
                    else:
                        command_successful = True


                if command_successful:
                    last_command_response = result
                    logger.typewriter_log(
                        "COMMAND EXECUTION SUCCESS", Fore.GREEN, ""
                    )
                    self.user_input = "COMMANDS EXECUTED! GENERATE NEXT JSON RESPONSE"
                else:
                    logger.typewriter_log(
                        "COMMAND EXECUTION FAILURE", Fore.RED, ""
                    )
                    self.user_input = f"THE {command_name} COMMAND FAILED. GENERATE NEXT JSON RESPONSE."

                memory_to_add = (
                    f"Assistant Reply: {assistant_reply} "
                    f"\nResult: {result} "
                    f"\nHuman Feedback: {user_input} "
                )

                self.memory.add(memory_to_add)

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