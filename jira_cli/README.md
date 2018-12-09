# CLI
custom JIRA-CLI
###### Requirements

  * Clone repo on your machine
  * Install required libs via python pip3
  * Python version >= 3

---

###### Required libs

* jira
* logging
* re
* sys
* random
* datetime
* termcolor
* time
* traceback
* functools
* json
* requests
* diskcache
* urllib3
* codecs
* argparse
* inquirer

---

###### How to install via Python pip3
```sh
pip3 install jira
```
###### How to run script
- interactive mode:
```sh
$ ./jira_cli_custom.py
```
Attention!
When you are entering a description in the interactive mode and you want to add a line break, please use: ```\\```
For code block, you may use: ```{code}some command here{code}```

###### ACHTUNG
If you use this script first time, you should start it in the interactive mode first time. However also you can provide credentials in the script.
Example: ```sh
credentials_for_jira = {"username": "test", "passwd": "123456"}
```
If you don't want to provide credentials as plain text in the script, it will ask your credentials for access to the JIRA and then,
it will try to encrypt them. Then, save into the file in the HOME directory.
When you get a message like: "Credentials safely stored" you may interupt 'interactive mode'.

- auto mode: create SubTask:
```sh
$ ./jira_cli_custom.py --auto --project_id "GMM" --ticket_id "GMM-35133" --issuetype "Sub-task" --summary "TEST 1" --description "TEST Subtask" --attachment "/Users/username/Pictures/18450.png"
```
- auto mode: create Task:
```sh
$ ./jira_cli_custom.py --auto --project_id "GMM" --ticket_id "GMM-35133" --issuetype "Task" --summary "TEST 2" --description "Another test task"
```

- auto mode: close Task:
```sh
$ ./jira_cli_custom.py --auto --project_id "GMM" --ticket_id "GMM-35378" --issuetype "Task" --transition "Closed" --description "It was test task and now it's closed."
```

- auto mode: reassign particular Task:
```sh
$ ./jira_cli_custom.py --auto --project_id "GMM" --issuetype "Task" --ticket_id "GMM-35444" --jira_assignee "jiras_username" --jira_reporter "jiras_username"
```
---
