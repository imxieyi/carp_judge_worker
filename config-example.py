import logging

login_url = 'http://localhost:8080/api/login?username={username}&password={password}'
server_url = 'ws://localhost:8765'
username = 'user'
password = 'password'
log_level = logging.DEBUG
parallel_judge_tasks = 2
log_limit_bytes = 256 * 1024
