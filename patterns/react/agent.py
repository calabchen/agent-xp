import importlib
import inspect
import json
import os
import pkgutil
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import tiktoken
from colorama import Fore, Style, init
from dotenv import load_dotenv
from openai import OpenAI

from tools.base_tool import BaseTool
from utils.message import Message


class ReActAgent:
    def __init__(self):
        load_dotenv()
        self.base_dir = Path(__file__).resolve().parent
        self.tools = {}
        self.messages = []
        self.max_iterations = 10
        self.current_iteration = 0
        self.old_chats_summary = ""
        self.messages_to_summarize = 3
        self.llm_max_tokens = 1024
        self.max_messages_tokens = 2048
        self.model = os.getenv("MODEL_NAME", "deepseek-chat")
        self.client = self.get_llm_client()
        self.system_prompt = self.load_prompt(self.base_dir / "system_prompt.md")
        self.summary_prompt = self.load_prompt(self.base_dir / "summary_prompt.md")
        self.tokenizer = self.get_tokenizer(self.model)
        self.register_tools()

    def get_tokenizer(self, model_name):
        """Get tokenizer for model, with fallback for non-OpenAI model names."""
        try:
            return tiktoken.encoding_for_model(model_name)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")

    def get_llm_client(self):
        llm_client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
        return llm_client

    def _instantiate_tool(self, tool_cls, module_name):
        """Instantiate tool classes that may require name/description args."""
        try:
            return tool_cls()
        except TypeError:
            sig = inspect.signature(tool_cls)
            kwargs = {}
            if "name" in sig.parameters:
                kwargs["name"] = getattr(tool_cls, "name", tool_cls.__name__.lower())
            if "description" in sig.parameters:
                kwargs["description"] = getattr(
                    tool_cls,
                    "description",
                    inspect.getdoc(tool_cls) or f"{module_name} tool",
                )
            return tool_cls(**kwargs)

    def register_tools(self):
        tool_modules = [name for _, name, _ in pkgutil.iter_modules(["tools"])]
        for module_name in tool_modules:
            try:
                module = importlib.import_module(f"tools.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseTool)
                        and attr is not BaseTool
                    ):
                        tool_instance = self._instantiate_tool(attr, module_name)
                        self.tools[tool_instance.name.lower()] = tool_instance
            except Exception as e:
                print(
                    f"\n{Fore.RED}[ERROR] Failed to register tool {module_name}: {e}{Style.RESET_ALL}\n"
                )

    def get_tools(self):
        """Returns a formatted string listing available tools."""
        return "\n".join(
            [f"{tool.name}: {tool.description}" for tool in self.tools.values()]
        )

    def count_tokens(self, value):
        """Return token count for plain text or chat-style message lists."""
        if isinstance(value, list):
            value = "".join(msg.get("content", "") for msg in value)
        encoded = self.tokenizer.encode(str(value))

        return len(encoded)

    def load_prompt(self, path):
        """Returns a prompt from a file."""
        with open(path, "rb") as file:
            raw = file.read()

        for encoding in ("utf-8", "utf-8-sig", "gbk"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode("utf-8", errors="replace")

    def add_message(self, role, content):
        """Add a message to the messages list."""
        self.messages.append(Message(role=role, content=content))

    def think(self):
        """Think and decide based on the response from OpenAI."""
        self.current_iteration += 1

        if self.current_iteration > self.max_iterations:
            print(
                f"\n{Fore.YELLOW}Reached maximum iterations. Stopping.{Style.RESET_ALL}"
            )
            self.add_message(
                "assistant",
                "I'm sorry, but I couldn't find a satisfactory answer within the allowed number of iterations.",
            )
            return

        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = self.system_prompt.format(tools=self.get_tools(), date=current_date)

        response = self.get_llm_response(prompt, stream_output=True)
        self.add_message("assistant", response)

        # Continue processing actions
        self.determine_action(response)

    def determine_action(self, response):
        """Decide on the next action based on the response, without using regex."""

        if "Final Answer:" in response:
            return

        # Find the line containing "Action:" (supports markdown output like "**Action:**")
        action_line = ""
        for line in response.splitlines():
            normalized_line = line.replace("**", "").strip()
            if normalized_line.lower().startswith("action:"):
                action_line = normalized_line
                break

        if not action_line:
            print(
                f"{Fore.YELLOW}No action or final answer found in the response.{Style.RESET_ALL}"
            )
            return

        # Remove the "Action:" prefix and parse "tool_name: query"
        action_body = action_line.split(":", 1)[1].strip()
        action_parts = action_body.split(":", 1)

        if len(action_parts) < 2:
            print(
                f"{Fore.RED}Error: Action format is incorrect: {action_line}{Style.RESET_ALL}"
            )
            return

        tool_name = action_parts[0].strip().lower().replace("**", "")
        tool_name = tool_name.strip("`*_ ")
        query = action_parts[1].strip()

        # Handle calculator JSON validation
        if tool_name == "calculator":
            try:
                json_data = json.loads(query)

                if "operation" not in json_data:
                    print(
                        f"{Fore.RED}Error: Missing 'operation' in calculator JSON: {query}{Style.RESET_ALL}"
                    )
                    return

                query = json.dumps(json_data)

            except json.JSONDecodeError:
                print(
                    f"{Fore.RED}Error: Invalid JSON input for calculator: {query}{Style.RESET_ALL}"
                )
                return

        # Execute the extracted action
        self.execute_action(tool_name, query)

    def execute_action(self, tool_name, query):
        """Act on the response by calling the appropriate tool."""
        tool = self.tools.get(tool_name)

        if tool:
            result = tool.run(query)
            observation = f"Observation: {tool_name} tool output: {result}"

            self.add_message("system", observation)

            # Print the observation immediately
            print(f"{Fore.CYAN}\n[SYSTEM]:{Style.RESET_ALL} {observation}\n")

            # Continue thinking after receiving observation
            self.think()
        else:
            error_msg = f"Error: Tool '{tool_name}' not found"
            print(f"\n{Fore.RED}{error_msg}{Style.RESET_ALL}")
            self.add_message("system", error_msg)
            self.think()  # Continue processing other actions

    def get_llm_response(self, prompt, stream_output=False):
        """Call the OpenAI API to get a response."""
        chat_history = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in self.messages
        ]

        self.memory_management(chat_history)

        if self.old_chats_summary:
            prompt += f"\n\nOld messages summary:\n{self.old_chats_summary}"

        messages = [{"role": "system", "content": prompt}] + chat_history
        messages_payload = cast(Any, messages)

        if stream_output:
            print(f"{Fore.GREEN}\n[ASSISTANT]:{Style.RESET_ALL} ", end="", flush=True)

        response_parts = []
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages_payload,
            max_tokens=self.llm_max_tokens,
            stream=True,
        )

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                response_parts.append(delta)
                if stream_output:
                    print(delta, end="", flush=True)

        if stream_output:
            print("\n")

        response = "".join(response_parts)

        return response.strip() if response else "No response from LLM"

    def summarize_old_chats(self, chats):
        """Summarizes old chat history and returns a concise summary response."""
        prompt = self.summary_prompt.format(chats=chats)
        messages = [{"role": "system", "content": prompt}]
        messages_payload = cast(Any, messages)

        raw_response = self.client.chat.completions.create(
            model=self.model, messages=messages_payload, max_tokens=self.llm_max_tokens
        )
        response = raw_response.choices[0].message.content

        return response.strip() if response else "No response from LLM"

    def get_indices(self, chat_history):
        """Extracts a specified number of consecutive user queries from the given chat history."""
        user_indices = [
            i for i, msg in enumerate(chat_history) if msg["role"] == "user"
        ]

        start_index = user_indices[0]
        end_index = user_indices[self.messages_to_summarize]

        return start_index, end_index

    def memory_management(self, chat_history):
        """Manages memory by summarizing and deleting old chat history"""
        try:
            user_messages = [msg for msg in chat_history if msg["role"] == "user"]
            if (
                len(user_messages) > self.messages_to_summarize
                and self.count_tokens(chat_history) > self.max_messages_tokens
            ):
                indices = self.get_indices(chat_history)
                if indices:
                    start_index, end_index = indices
                    chats = chat_history[start_index:end_index]
                    new_summary = self.summarize_old_chats(chats)
                    print(
                        f"##### Tokens used by the old messages: {self.count_tokens(chats)}"
                    )
                    # print("##### New Summary : ", new_summary)
                    if new_summary != "No response from LLM":
                        print(
                            f"##### Tokens used by the new summary: {self.count_tokens(new_summary)}"
                        )
                        self.old_chats_summary = (
                            f"{self.old_chats_summary} {new_summary}".strip()
                        )
                        print("##### Old messages summary : ", self.old_chats_summary)
                        del self.messages[start_index:end_index]
        except Exception as e:
            print(f"An error occurred during memory management: {e}")

    def execute(self, query):
        """Execute a user query and return the full Agent response."""
        self.current_iteration = 0
        self.add_message("user", query)
        self.think()

        result_messages = []
        for message in self.messages[::-1]:
            if message.role == "user":
                break
            elif message.role != "user":
                result_messages.append(message)

        return result_messages[::-1]


if __name__ == "__main__":
    init(autoreset=True)
    react_agent = ReActAgent()

    while True:
        query = input(f"{Fore.CYAN}USER:{Style.RESET_ALL} ").strip()
        if query.lower() in ["exit", "quit"]:
            print(f"{Fore.YELLOW}Exiting the ReAct agent. Goodbye!{Style.RESET_ALL}")
            break

        result = react_agent.execute(query)
        # print('#### Result : ', result)
        print("\n" + "=" * 60 + "\n")
