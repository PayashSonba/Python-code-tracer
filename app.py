from flask import Flask, render_template, request, jsonify, session
import json
import uuid
import time
import threading
from main import DynamicCodeTracer  # Import from your existing main.py

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Store tracers in memory
tracers = {}
processing_tasks = {}

@app.route('/')
def index():
    """Main page with code input form."""
    return render_template('index.html')

@app.route('/trace', methods=['POST'])
def trace_code():
    """Process code and return tracing steps with timeout."""
    try:
        data = request.get_json()
        source_code = data.get('code', '').strip()
        
        if not source_code:
            return jsonify({'error': 'No code provided'}), 400
        
        # Quick safety checks
        if len(source_code.splitlines()) > 50:
            return jsonify({'error': 'Code too long (max 50 lines for web version)'}), 400
        
        if any(danger in source_code for danger in ['while True', 'time.sleep', 'input(']):
            return jsonify({'error': 'Code contains potentially blocking operations'}), 400
        
        # Create unique session ID
        session_id = str(uuid.uuid4())
        
        # Process with timeout
        result = {'steps': None, 'error': None}
        
        def process_code():
            try:
                tracer = DynamicCodeTracer(source_code)
                result['steps'] = tracer.steps
                result['source_lines'] = tracer.source_lines
            except Exception as e:
                result['error'] = str(e)
        
        # Run with timeout
        thread = threading.Thread(target=process_code)
        thread.daemon = True
        thread.start()
        thread.join(timeout=10)  # 10 second timeout
        
        if thread.is_alive():
            return jsonify({'error': 'Code execution timed out (10s limit)'}), 400
        
        if result['error']:
            return jsonify({'error': result['error']}), 400
        
        if not result['steps']:
            return jsonify({'error': 'No executable steps found in the code'}), 400
        
        # Store tracer for this session
        tracers[session_id] = {
            'steps': result['steps'],
            'source_lines': result['source_lines'],
            'created': time.time()
        }
        
        # Convert steps to JSON-serializable format
        steps_data = []
        for step in result['steps']:
            steps_data.append({
                'line_num': step.line_num,
                'source_line': step.source_line,
                'explanation': step.explanation,
                'variables': step.variables,
                'iteration_info': step.iteration_info
            })
        
        return jsonify({
            'session_id': session_id,
            'steps': steps_data,
            'total_steps': len(steps_data),
            'source_lines': result['source_lines']
        })
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/step/<session_id>/<int:step_num>')
def get_step(session_id, step_num):
    """Get specific step data."""
    try:
        if session_id not in tracers:
            return jsonify({'error': 'Session not found'}), 404
        
        tracer_data = tracers[session_id]
        steps = tracer_data['steps']
        
        if step_num < 0 or step_num >= len(steps):
            return jsonify({'error': 'Invalid step number'}), 400
        
        step = steps[step_num]
        return jsonify({
            'line_num': step.line_num,
            'source_line': step.source_line,
            'explanation': step.explanation,
            'variables': step.variables,
            'iteration_info': step.iteration_info,
            'current_step': step_num + 1,
            'total_steps': len(steps)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/examples')
def examples():
    """Return simple example code snippets."""
    examples = {
        'basic_loop': '''# Simple For Loop
for i in range(3):
    x = i * 2
    print(f"i={i}, x={x}")''',
        
        'variables': '''# Variable Operations
a = 5
b = 10
c = a + b
print(f"Sum: {c}")''',
        
        'list_simple': '''# Basic List
numbers = [1, 2, 3]
for num in numbers:
    doubled = num * 2
    print(doubled)''',
        
        'fibonacci': '''# Fibonacci (first 5)
a, b = 0, 1
for i in range(5):
    print(a)
    a, b = b, a + b'''
    }
    
    return jsonify(examples)

# Cleanup old sessions periodically
def cleanup_old_sessions():
    """Remove sessions older than 1 hour."""
    current_time = time.time()
    to_remove = []
    
    for session_id, data in tracers.items():
        if current_time - data['created'] > 3600:  # 1 hour
            to_remove.append(session_id)
    
    for session_id in to_remove:
        del tracers[session_id]

# Run cleanup every 30 minutes
def start_cleanup_thread():
    def cleanup_loop():
        while True:
            time.sleep(1800)  # 30 minutes
            cleanup_old_sessions()
    
    thread = threading.Thread(target=cleanup_loop)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    start_cleanup_thread()
    app.run(debug=True, host='0.0.0.0', port=5050)