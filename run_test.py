import subprocess

with open('tests/test_dashboard_savings_by_model.py') as f:
    code = f.read()
code = code.replace('page.on("console", lambda msg: print(f"Browser console: {msg.text}"))',
                    'page.on("console", lambda msg: print(f"Browser console: {msg.text}"))\n            page.on("request", lambda request: print(">>", request.method, request.url))\n            page.on("response", lambda response: print("<<", response.status, response.url))')
with open('tests/test_dashboard_savings_by_model.py', 'w') as f:
    f.write(code)

result = subprocess.run(["pytest", "tests/test_dashboard_savings_by_model.py", "-s"], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
