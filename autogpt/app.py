""" Command and Control """
import json
from typing import Dict, List, NoReturn, Union

from autogpt.agent.agent_manager import AgentManager
from autogpt.commands.analyze_code import analyze_code
from autogpt.commands.audio_text import read_audio_from_file
from autogpt.commands.execute_code import (
    execute_python_file,
    execute_shell,
    execute_shell_popen,
)
from autogpt.commands.file_operations import (
    append_to_file,
    create_file,
    delete_file,
    download_file,
    file_exists,
    read_file,
    replace_in_file,
    search_files,
    write_to_file,
)
from autogpt.commands.git_operations import clone_repository
from autogpt.commands.google_search import google_official_search, google_search
from autogpt.commands.image_gen import generate_image
from autogpt.commands.improve_code import improve_code
from autogpt.commands.twitter import send_tweet
from autogpt.commands.web_requests import scrape_links, scrape_text
from autogpt.commands.web_selenium import browse_website
from autogpt.commands.write_tests import write_tests
from autogpt.config import Config
from autogpt.json_utils.json_fix_llm import fix_and_parse_json
from autogpt.memory import get_memory
from autogpt.processing.text import summarize_text
from autogpt.speech import say_text
from autogpt.llm_utils import call_ai_function, create_chat_completion

CFG = Config()
AGENT_MANAGER = AgentManager()


def is_valid_int(value: str) -> bool:
    """Check if the value is a valid integer

    Args:
        value (str): The value to check

    Returns:
        bool: True if the value is a valid integer, False otherwise
    """
    try:
        int(value)
        return True
    except ValueError:
        return False

def get_commands(response: Dict):
    """Parse the response and return the list of commmands

    Args:
        response_json (json): The response from the AI

    Returns:
        list: The list of commands

    Raises:
        json.decoder.JSONDecodeError: If the response is not valid JSON

        Exception: If any other error occurs
    """
    try:
        response_json = fix_and_parse_json(response)

        if "commands" not in response_json:
            logger.debug("\n\n Missing 'commands' object in JSON \n\n")
            return "Error:", "Missing 'commands' object in JSON"

        if not isinstance(response_json, dict):
            logger.debug("\n\n 'response_json' object is not dictionary \n\n")
            return "Error:", f"'response_json' object is not dictionary {response_json}"

        commands = response_json["commands"]
        if not isinstance(commands, list):
            return "Error:", "'commands' object is not a list"


        for command in commands:
            if "name" not in command:
                return "Error:", f"Missing 'name' field in {command}"

            # Use an empty dictionary if 'args' field is not present in 'command' object
            if "args" not in command or not isinstance(command.get("args"), dict):
                command.set("args", {})

        return commands
    except json.decoder.JSONDecodeError:
        return "Error:", "Invalid JSON"
    # All other errors, return "Error: + error message"
    except Exception as e:
        return "Error:", str(e)

def get_command(response_json: Dict):
    """Parse the response and return the command name and arguments

    Args:
        response_json (json): The response from the AI

    Returns:
        tuple: The command name and arguments

    Raises:
        json.decoder.JSONDecodeError: If the response is not valid JSON

        Exception: If any other error occurs
    """
    try:
        if "command" not in response_json:
            return "Error:", "Missing 'command' object in JSON"

        if not isinstance(response_json, dict):
            return "Error:", f"'response_json' object is not dictionary {response_json}"

        command = response_json["command"]
        if not isinstance(command, dict):
            return "Error:", "'command' object is not a dictionary"

        if "name" not in command:
            return "Error:", "Missing 'name' field in 'command' object"

        command_name = command["name"]

        # Use an empty dictionary if 'args' field is not present in 'command' object
        arguments = command.get("args", {})

        return command_name, arguments
    except json.decoder.JSONDecodeError:
        return "Error:", "Invalid JSON"
    # All other errors, return "Error: + error message"
    except Exception as e:
        return "Error:", str(e)


def map_command_synonyms(command_name: str):
    """Takes the original command name given by the AI, and checks if the
    string matches a list of common/known hallucinations
    """
    synonyms = [
        ("write_file", "write_to_file"),
        #("create_file", "write_to_file"),
        ("search", "google"),
    ]
    for seen_command, actual_command_name in synonyms:
        if command_name == seen_command:
            return actual_command_name
    return command_name


def execute_command(command_name: str, arguments):
    """Execute the command and return the result

    Args:
        command_name (str): The name of the command to execute
        arguments (dict): The arguments for the command

    Returns:
        str: The result of the command
    """
    try:
        command_name = map_command_synonyms(command_name.lower())
        if command_name == "google":
            # Check if the Google API key is set and use the official search method
            # If the API key is not set or has only whitespaces, use the unofficial
            # search method
            key = CFG.google_api_key
            if key and key.strip() and key != "your-google-api-key":
                google_result = google_official_search(arguments["input"])
                return google_result
            else:
                google_result = google_search(arguments["input"])

            # google_result can be a list or a string depending on the search results
            if isinstance(google_result, list):
                safe_message = [
                    google_result_single.encode("utf-8", "ignore")
                    for google_result_single in google_result
                ]
            else:
                safe_message = google_result.encode("utf-8", "ignore")

            return safe_message.decode("utf-8")
        elif command_name == "save_to_db":
            memory = get_memory(CFG)
            return memory.add(f"{arguments['key']}:{arguments['value']}")
        elif command_name == "load_from_db":
            memory = get_memory(CFG)
            return memory.get(arguments["key"])
        elif command_name == "ask_gpt4":
            return create_chat_completion(
                model=CFG.smart_llm_model,
                messages=[{"role": "system", "content": "you are a smart assistant"}, {"role": "user", "content": arguments["prompt"]}],
                max_tokens=8000,
            )
        elif command_name == "start_agent":
            return start_agent(
                arguments["name"], arguments["task"], arguments["prompt"]
            )
        elif command_name == "ask_agent":
            return message_agent(arguments["key"], arguments["prompt"])
        elif command_name == "list_agents":
            return list_agents()
        elif command_name == "delete_agent":
            return delete_agent(arguments["key"])
        elif command_name == "get_text_summary":
            return get_text_summary(arguments["url"], arguments["question"])
        elif command_name == "get_hyperlinks":
            return get_hyperlinks(arguments["url"])
        elif command_name == "clone_repository":
            return clone_repository(
                arguments["repository_url"], arguments["clone_path"]
            )
        elif command_name == "read_file":
            return read_file(arguments["file"])
        elif command_name == "write_to_file":
            return write_to_file(arguments["file"], arguments["text"])
        elif command_name == "append_to_file":
            return append_to_file(arguments["file"], arguments["text"])
        elif command_name == "delete_file":
            return delete_file(arguments["file"])
        elif command_name == "search_files":
            return search_files(arguments["directory"])
        elif command_name == "download_file":
            if not CFG.allow_downloads:
                return "Error: You do not have user authorization to download files locally."
            return download_file(arguments["url"], arguments["file"])
        elif command_name == "browse_website":
            return browse_website(arguments["url"], arguments["question"])
        # TODO: Change these to take in a file rather than pasted code, if
        # non-file is given, return instructions "Input should be a python
        # filepath, write your code to file and try again"
        elif command_name == "analyze_code":
            return analyze_code(arguments["code"])
        elif command_name == "improve_code":
            return improve_code(arguments["suggestions"], arguments["code"])
        elif command_name == "write_tests":
            return write_tests(arguments["code"], arguments.get("focus"))
        elif command_name == "execute_python_file":  # Add this command
            return execute_python_file(arguments["file"])
        elif command_name == "execute_shell":
            if CFG.execute_local_commands:
                return execute_shell(arguments["command_line"])
            else:
                return (
                    "You are not allowed to run local shell commands. To execute"
                    " shell commands, EXECUTE_LOCAL_COMMANDS must be set to 'True' "
                    "in your config. Do not attempt to bypass the restriction."
                )
        elif command_name == "execute_shell_popen":
            if CFG.execute_local_commands:
                return execute_shell_popen(arguments["command_line"])
            else:
                return (
                    "You are not allowed to run local shell commands. To execute"
                    " shell commands, EXECUTE_LOCAL_COMMANDS must be set to 'True' "
                    "in your config. Do not attempt to bypass the restriction."
                )
        elif command_name == "read_audio_from_file":
            return read_audio_from_file(arguments["file"])
        elif command_name == "generate_image":
            return generate_image(arguments["prompt"])
        elif command_name == "send_tweet":
            return send_tweet(arguments["text"])
        elif command_name == "do_nothing":
            return "No action performed."
        elif command_name == "task_complete":
            shutdown()
        elif command_name == "create_file":
            return create_file(arguments["file"])
        elif command_name == "replace_in_file":
            return replace_in_file(
                arguments["file"], arguments["text"], arguments["new_text"]
            )
        elif command_name == "file_exists":
            return file_exists(arguments["file"])
        else:
            return (
                f"Unknown command '{command_name}'. Please refer to the 'COMMANDS'"
                " list for available commands and only respond in the specified JSON"
                " format."
            )
    except Exception as e:
        return f"Error: {str(e)}"


def get_text_summary(url: str, question: str) -> str:
    """Return the results of a Google search

    Args:
        url (str): The url to scrape
        question (str): The question to summarize the text for

    Returns:
        str: The summary of the text
    """
    text = scrape_text(url)
    summary = summarize_text(url, text, question)
    return f""" "Result" : {summary}"""


def get_hyperlinks(url: str) -> Union[str, List[str]]:
    """Return the results of a Google search

    Args:
        url (str): The url to scrape

    Returns:
        str or list: The hyperlinks on the page
    """
    return scrape_links(url)


def shutdown() -> NoReturn:
    """Shut down the program"""
    print("Shutting down...")
    quit()


def start_agent(name: str, task: str, prompt: str, model=CFG.fast_llm_model) -> str:
    """Start an agent with a given name, task, and prompt

    Args:
        name (str): The name of the agent
        task (str): The task of the agent
        prompt (str): The prompt for the agent
        model (str): The model to use for the agent

    Returns:
        str: The response of the agent
    """
    # Remove underscores from name
    voice_name = name.replace("_", " ")

    first_message = f"""You are {name}.  Respond with: "Acknowledged"."""
    agent_intro = f"{voice_name} here, Reporting for duty!"

    # Create agent
    if CFG.speak_mode:
        say_text(agent_intro, 1)
    key, ack = AGENT_MANAGER.create_agent(name, task, first_message, model)

    if CFG.speak_mode:
        say_text(f"Hello {voice_name}. Your task is as follows. {task}.")

    # Assign task (prompt), get response
    agent_response = AGENT_MANAGER.message_agent(key, prompt)

    return f"Agent {name} created with key {key}. First response: {agent_response}"


def message_agent(key: str, message: str) -> str:
    """Message an agent with a given key and message"""
    # Check if the key is a valid integer
    #if is_valid_int(key):
    agent_response = AGENT_MANAGER.message_agent(key, message)
    #else:
    #    return "Invalid key, must be an integer."

    # Speak response
    if CFG.speak_mode:
        say_text(agent_response, 1)
    return agent_response


def list_agents():
    """List all agents

    Returns:
        str: A list of all agents
    """
    return "List of agents:\n" + "\n".join(
        [str(x[0]) + ": " + x[1] for x in AGENT_MANAGER.list_agents()]
    )


def delete_agent(key: str) -> str:
    """Delete an agent with a given key

    Args:
        key (str): The key of the agent to delete

    Returns:
        str: A message indicating whether the agent was deleted or not
    """
    result = AGENT_MANAGER.delete_agent(key)
    return f"Agent {key} deleted." if result else f"Agent {key} does not exist."

def cmd_response_needs_verification(command_name):
    """Return True if the command requires verification"""
    if command_name in [
        "prompt_agent",
    ]:
        return True
    else:
        return False

def parse_cmd_response(command:str, arguments:str, response:str) -> bool:
    """Get the command result."""
    # Try to fix the JSON using GPT:
    function_string = "def parse_cmd_response(command:str, arguments:str, response:str) -> bool:"
    args = [f"'''{command}'''", f"'''{arguments}'''", f"'''{response}'''"]
    description_string = (
        "Check if the command response is valid. This is used to determine if the"
        " command was successful or not. Returns True if the command response indicates"
        " success, and False otherwise.\n"
        "This function is brilliant at guessing when the command was successful"
    )
    result_string = call_ai_function(
        function_string, args, description_string, model=CFG.fast_llm_model
    )
    if "True" in result_string:
        return True
    else:
        return False