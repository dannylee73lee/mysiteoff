2026-04-18 00:28:38.006 Uncaught app execution
Traceback (most recent call last):
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/runtime/scriptrunner/exec_code.py", line 129, in exec_func_with_error_handling
    result = func()
             ^^^^^^
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/runtime/scriptrunner/script_runner.py", line 687, in code_to_exec
    _mpa_v1(self._main_script_path)
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/runtime/scriptrunner/script_runner.py", line 166, in _mpa_v1
    page.run()
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/navigation/page.py", line 490, in run
    exec(code, module.__dict__)  # noqa: S102
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspaces/mysiteoff/streamlit_app.py", line 65, in <module>
    st.page_link("app.py",                        label="📊 메인 현황")
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/runtime/metrics_util.py", line 563, in wrapped_func
    result = non_optional_func(*args, **kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/elements/widgets/button.py", line 1288, in page_link
    return self._page_link(
           ^^^^^^^^^^^^^^^^
  File "/home/vscode/.local/lib/python3.11/site-packages/streamlit/elements/widgets/button.py", line 1602, in _page_link
    raise StreamlitPageNotFoundError(
streamlit.errors.StreamlitPageNotFoundError: Could not find page: `app.py`. You must provide a file path relative to the entrypoint file (from the directory `mysiteoff`). Only the entrypoint file and files in the `pages/` directory are supported.