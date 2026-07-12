"""Calculator skill for Jarvis."""
import math
import re
from typing import Any, Dict

from src.skills.registry import Skill


class CalculatorSkill(Skill):
    """Mathematical calculations skill."""

    name = "calculator"
    description = "Perform mathematical calculations"
    triggers = ["calculate", "calc", "math", "compute", "solve", "="]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute calculation."""
        text = context.get("text", "") if context else ""
        expression = params.get("expression", self._extract_expression(text))

        if not expression:
            return "What would you like me to calculate?"

        return self._calculate(expression)

    def _extract_expression(self, text: str) -> str:
        """Extract mathematical expression from text."""
        # Remove trigger words
        text = re.sub(r'\b(calculate|calc|math|compute|solve)\b', '', text, flags=re.IGNORECASE)
        text = text.strip()

        # If it ends with =, remove it
        if text.endswith('='):
            text = text[:-1].strip()

        return text

    def _calculate(self, expression: str) -> str:
        """Safely evaluate mathematical expression."""
        # Allowed names
        allowed_names = {
            k: v for k, v in math.__dict__.items() if not k.startswith("__")
        }
        allowed_names.update({
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
        })

        # Sanitize expression
        expression = expression.replace("^", "**")
        expression = expression.replace("×", "*")
        expression = expression.replace("÷", "/")
        expression = expression.replace("π", "pi")
        expression = expression.replace("√", "sqrt")

        try:
            # Parse to check for safety
            code = compile(expression, "<string>", "eval")
            for name in code.co_names:
                if name not in allowed_names:
                    return f"Error: Use of '{name}' not allowed"

            result = eval(code, {"__builtins__": {}}, allowed_names)
            return f"{expression} = {result}"
        except SyntaxError:
            return f"Error: Invalid expression syntax"
        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error: {e}"