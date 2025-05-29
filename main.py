import ast
import os
import sys
import traceback
from pathlib import Path
from types import FrameType
from typing import Dict, Any, List, Tuple

#Hey this is my new SSH key!


class ExecutionStep:
    """Represents a single step in code execution with actual variable values."""
    def __init__(self, line_num: int, source_line: str, explanation: str, 
                 variables: Dict[str, Any] = None, iteration_info: str = None):
        self.line_num = line_num
        self.source_line = source_line.strip() if source_line else ""
        self.explanation = explanation
        self.variables = variables or {}
        self.iteration_info = iteration_info  # For loop iteration tracking

class DynamicCodeTracer:
    """Dynamic step-by-step code tracer that actually executes code."""
    
    def __init__(self, source_code: str):
        self.source_lines = source_code.splitlines()
        self.steps: List[ExecutionStep] = []
        self.current_line = 0
        self.loop_stack = []  # Track nested loops
        self.execution_context = {}
        
        # Try to trace the code dynamically
        self._trace_code_dynamically(source_code)
    
    def _trace_code_dynamically(self, source_code: str):
        """Execute code with line-by-line tracing."""
        def trace_calls(frame: FrameType, event: str, arg):
            if event == 'line':
                self._handle_line_execution(frame)
            elif event == 'call':
                # Handle function calls
                func_name = frame.f_code.co_name
                if func_name != '<module>':
                    self._add_step_from_frame(frame, f"Enter function '{func_name}'")
            elif event == 'return':
                # Handle function returns
                func_name = frame.f_code.co_name
                if func_name != '<module>':
                    return_value = arg if arg is not None else "None"
                    self._add_step_from_frame(frame, f"Return from '{func_name}': {return_value}")
            return trace_calls
        
        try:
            # Set up tracing
            old_trace = sys.gettrace()
            sys.settrace(trace_calls)
            
            # Execute the code
            exec(source_code, self.execution_context)
            
        except Exception as e:
            # Add error step
            error_line = getattr(e, 'lineno', self.current_line)
            self._add_step(error_line, f"ERROR: {str(e)}", "Execution stopped due to error", {})
        finally:
            # Restore original trace function
            sys.settrace(old_trace)
    
    def _handle_line_execution(self, frame: FrameType):
        """Handle execution of each line."""
        line_num = frame.f_lineno
        
        # Skip if we've already processed this exact line in this context
        if line_num == self.current_line:
            return
            
        self.current_line = line_num
        
        # Get current source line
        if line_num <= len(self.source_lines):
            source_line = self.source_lines[line_num - 1]
        else:
            source_line = ""
        
        # Get current variables (local variables from frame)
        current_vars = dict(frame.f_locals)
        
        # Remove built-in variables and functions
        filtered_vars = {k: v for k, v in current_vars.items() 
                        if not k.startswith('__') and not callable(v)}
        
        # Generate explanation based on the source line
        explanation = self._generate_explanation(source_line, filtered_vars)
        
        # Check if we're in a loop and add iteration info
        iteration_info = self._get_loop_iteration_info(source_line, filtered_vars)
        
        self._add_step(line_num, source_line, explanation, filtered_vars, iteration_info)
    
    def _add_step_from_frame(self, frame: FrameType, explanation: str):
        """Add a step from frame information."""
        line_num = frame.f_lineno
        source_line = self.source_lines[line_num - 1] if line_num <= len(self.source_lines) else ""
        current_vars = {k: v for k, v in frame.f_locals.items() 
                       if not k.startswith('__') and not callable(v)}
        
        self._add_step(line_num, source_line, explanation, current_vars)
    
    def _generate_explanation(self, source_line: str, variables: Dict[str, Any]) -> str:
        """Generate human-readable explanation for the source line."""
        line = source_line.strip()
        
        if not line or line.startswith('#'):
            return "Comment or empty line"
        
        # Assignment operations
        if '=' in line and not any(op in line for op in ['==', '!=', '<=', '>=']):
            if '+=' in line:
                var_name = line.split('+=')[0].strip()
                return f"Increment '{var_name}' by the value on the right"
            elif '-=' in line:
                var_name = line.split('-=')[0].strip()
                return f"Decrement '{var_name}' by the value on the right"
            elif '*=' in line:
                var_name = line.split('*=')[0].strip()
                return f"Multiply '{var_name}' by the value on the right"
            elif '/=' in line:
                var_name = line.split('/=')[0].strip()
                return f"Divide '{var_name}' by the value on the right"
            else:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    var_name = parts[0].strip()
                    value = parts[1].strip()
                    return f"Assign {value} to variable '{var_name}'"
        
        # Control structures
        if line.startswith('for '):
            return f"Start for loop: {line}"
        elif line.startswith('while '):
            return f"Check while condition: {line}"
        elif line.startswith('if '):
            return f"Check if condition: {line}"
        elif line.startswith('elif '):
            return f"Check elif condition: {line}"
        elif line.startswith('else:'):
            return "Execute else block"
        
        # Function definitions
        if line.startswith('def '):
            func_name = line.split('(')[0].replace('def ', '').strip()
            return f"Define function '{func_name}'"
        
        # Print statements
        if line.strip().startswith('print('):
            return f"Print output: {line}"
        
        # Return statements
        if line.startswith('return'):
            return f"Return: {line}"
        
        # Break and continue
        if line.strip() == 'break':
            return "Break out of current loop"
        elif line.strip() == 'continue':
            return "Skip to next iteration of loop"
        
        # Default
        return f"Execute: {line}"
    
    def _get_loop_iteration_info(self, source_line: str, variables: Dict[str, Any]) -> str:
        """Get information about current loop iteration."""
        line = source_line.strip()
        
        # Check for common loop variables
        loop_vars = ['i', 'j', 'k', 'n', 'x', 'y', 'index', 'count']
        current_loop_vars = {}
        
        for var in loop_vars:
            if var in variables and isinstance(variables[var], (int, float)):
                current_loop_vars[var] = variables[var]
        
        if current_loop_vars:
            info_parts = [f"{var}={val}" for var, val in current_loop_vars.items()]
            return f"Loop variables: {', '.join(info_parts)}"
        
        return None
    
    def _add_step(self, line_num: int, source_line: str, explanation: str, 
                  variables: Dict[str, Any], iteration_info: str = None):
        """Add an execution step."""
        # Format variables for display
        display_vars = {}
        for k, v in variables.items():
            if isinstance(v, str):
                display_vars[k] = f'"{v}"'
            elif isinstance(v, list):
                if len(v) <= 5:
                    display_vars[k] = str(v)
                else:
                    display_vars[k] = f"list[{len(v)} items]: {str(v[:3])}..."
            elif isinstance(v, dict):
                if len(v) <= 3:
                    display_vars[k] = str(v)
                else:
                    display_vars[k] = f"dict[{len(v)} items]"
            else:
                display_vars[k] = str(v)
        
        step = ExecutionStep(line_num, source_line, explanation, display_vars, iteration_info)
        self.steps.append(step)

class StepNavigator:
    """Enhanced step-by-step navigation interface."""
    
    def __init__(self, tracer: DynamicCodeTracer):
        self.tracer = tracer
        self.current_step = 0
    
    def clear_screen(self):
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_step(self):
        """Display current step with enhanced formatting."""
        self.clear_screen()
        
        if not self.tracer.steps:
            print("❌ No execution steps available.")
            return
        
        step = self.tracer.steps[self.current_step]
        total_steps = len(self.tracer.steps)
        
        print("=" * 80)
        print(f"🐍 PYTHON CODE TRACER - Step {self.current_step + 1}/{total_steps}")
        print("=" * 80)
        
        print(f"\n📍 LINE {step.line_num}:")
        print(f"   {step.source_line}")
        
        print(f"\n💡 EXPLANATION:")
        print(f"   {step.explanation}")
        
        if step.iteration_info:
            print(f"\n🔄 LOOP INFO:")
            print(f"   {step.iteration_info}")
        
        print(f"\n📊 VARIABLES:")
        if step.variables:
            # Sort variables for consistent display
            for var_name in sorted(step.variables.keys()):
                value = step.variables[var_name]
                print(f"   {var_name} = {value}")
        else:
            print("   (No variables to display)")
        
        print("\n" + "─" * 80)
        print("Commands: [n]ext | [p]revious | [j]ump to step | [q]uit")
        print("─" * 80)
        print("➤ ", end="")
    
    def navigate(self):
        """Enhanced navigation loop."""
        if not self.tracer.steps:
            print("❌ No steps to navigate.")
            return
        
        while True:
            self.display_step()
            
            try:
                command = input().strip().lower()
                
                if command == 'n' or command == '':  # Allow Enter for next
                    if self.current_step < len(self.tracer.steps) - 1:
                        self.current_step += 1
                    else:
                        print("\n✋ You are at the last step.")
                        input("Press Enter to continue...")
                
                elif command == 'p':
                    if self.current_step > 0:
                        self.current_step -= 1
                    else:
                        print("\n✋ You are at the first step.")
                        input("Press Enter to continue...")
                
                elif command == 'j':
                    try:
                        target = int(input("Jump to step number (1-{}): ".format(len(self.tracer.steps))))
                        if 1 <= target <= len(self.tracer.steps):
                            self.current_step = target - 1
                        else:
                            print(f"❌ Invalid step number. Must be between 1 and {len(self.tracer.steps)}")
                            input("Press Enter to continue...")
                    except ValueError:
                        print("❌ Please enter a valid number.")
                        input("Press Enter to continue...")
                
                elif command == 'q':
                    print("\n👋 Exiting tracer.")
                    break
                
                else:
                    print("\n❓ Invalid command. Use:")
                    print("  'n' or Enter - Next step")
                    print("  'p' - Previous step") 
                    print("  'j' - Jump to specific step")
                    print("  'q' - Quit")
                    input("Press Enter to continue...")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Navigation interrupted.")
                break
            except EOFError:
                print("\n\n👋 Exiting tracer.")
                break

def main():
    """Main function with enhanced interface."""
    print("🐍 DYNAMIC PYTHON CODE TRACER")
    print("=" * 50)
    print("📚 Perfect for understanding code execution step-by-step!")
    print("🎯 Shows actual variable values as they change during loops")
    print("=" * 50)
    
    file_path = input("\n📁 Enter the path to the Python file: ").strip()
    
    if not file_path:
        print("❌ No file path provided.")
        return
    
    try:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ File not found: {file_path}")
            return
        
        if not path.is_file():
            print(f"❌ Path is not a file: {file_path}")
            return
        
        print(f"✅ Loading file: {path.name}")
        
        with open(path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        if not source_code.strip():
            print("⚠️ File appears to be empty.")
            return
        
        print("🔄 Analyzing and executing code...")
        tracer = DynamicCodeTracer(source_code)
        
        if not tracer.steps:
            print("❌ No executable steps found in the code.")
            return
        
        print(f"✅ Generated {len(tracer.steps)} execution steps.")
        print("\n🎯 TIP: Use 'n' or just press Enter to go to the next step!")
        input("\nPress Enter to start step-by-step navigation...")
        
        navigator = StepNavigator(tracer)
        navigator.navigate()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()