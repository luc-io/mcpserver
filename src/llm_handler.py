from typing import Optional, Dict, List
import os
import logging
from anthropic import Anthropic
import json

logger = logging.getLogger(__name__)

class LLMHandler:
    def __init__(self):
        self.anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.context = {}
        self.functions = {}

    def register_function(self, name: str, func, description: str, parameters: Dict = None):
        """Register a function that the LLM can call"""
        self.functions[name] = {
            "function": func,
            "description": description,
            "parameters": parameters
        }

    def get_available_functions(self) -> str:
        """Get formatted list of available functions"""
        functions_list = []
        for name, info in self.functions.items():
            function_desc = f"{name}: {info['description']}"
            if info['parameters']:
                function_desc += f"\nParameters: {json.dumps(info['parameters'], indent=2)}"
            functions_list.append(function_desc)
        return "\n\n".join(functions_list)

    async def process_message(self, message: str, context: Optional[Dict] = None) -> str:
        """Process a message using Claude and execute any requested functions"""
        try:
            # Prepare system message with available functions
            system_message = f"""You are an AI assistant with access to these functions:

{self.get_available_functions()}

When a user requests an action that requires one of these functions, format your response as:
<function_call>
{{"name": "function_name", "parameters": {{...}}}}
</function_call>

Then wait for the function result before continuing the conversation.
"""

            # Create message history
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": message}
            ]

            # Get LLM response
            response = await self.anthropic.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=2048,
                messages=messages
            )

            # Extract and execute any function calls
            if "<function_call>" in response.content:
                start = response.content.index("<function_call>") + len("<function_call>")
                end = response.content.index("</function_call>")
                function_data = json.loads(response.content[start:end])
                
                # Execute function
                if function_data["name"] in self.functions:
                    func_info = self.functions[function_data["name"]]
                    result = await func_info["function"](**function_data.get("parameters", {}))
                    
                    # Get final response with function result
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": f"Function result: {json.dumps(result)}"})
                    final_response = await self.anthropic.messages.create(
                        model="claude-3-opus-20240229",
                        max_tokens=2048,
                        messages=messages
                    )
                    return final_response.content
                else:
                    return f"Error: Function {function_data['name']} not found"

            return response.content

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return f"Error processing message: {str(e)}"
