# One pure-Python package for both Linux and Windows

server-motd is a single Python package (3.11+, `psutil` the only third-party dependency) rather than bash fragments plus a Python helper, or parallel Bash and PowerShell codebases. A bash/PowerShell split would need every service client written twice, and rTorrent's XML-RPC is impractical in shell; Ansible already requires Python on managed Linux hosts, so Python costs nothing there. The cost is that Windows needs Python installed (via `pipx`).
