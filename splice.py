path = '/home/remvelchio/agent/eigentrace.py'
with open(path) as f:
    content = f.read()
start = content.index('def compute_trace_metrics')
end = content.index('def log_telemetry')
with open('/home/remvelchio/agent/new_func.py') as f:
    new_func = f.read()
content = content[:start] + new_func + '\n' + content[end:]
with open(path, 'w') as f:
    f.write(content)
print('OK: spliced')
