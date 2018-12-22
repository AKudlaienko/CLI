#!/usr/bin/python3

import datetime
import time

# time period for sending emails to the same thread if trigger was not change his state
email_hours_same_thread = 24
# time gap during which AUTO-emails will not working
from_time = datetime.datetime.strptime('23:55:00', '%H:%M:%S').time()
to_time = datetime.datetime.strptime('00:40:00', '%H:%M:%S').time()
# Mail server address
mail_server_address = 'your_relay'
log_file = '/tmp/download_zab_graph_main.log'

# ----------------Zabbix servers and login info----------------------------------------
# The format is next:
# 'dev' - short name of Zabbix location; 'http://dev-zabbix.org/' - address
zabbix_hosts = {
    'dev': 'http://dev-zabbix.org/',
    'staging': 'http://staging-zabbix.org/',
    'user': 'your_zabbix_api_user',
    'zabbix_pass': 'your_zabbix_api_passowrd'
}

# ------------MySQL info ------------------------------------------------------------
# DB name should be 'automations'. All tables should be in this database
# obligatory table: wiki_syncer -- there where data from WIKI located
# obligatory table: at list one table like a table in dict: zabbix_auto_tables
mysql_user = 'your_DB_user'
mysql_password = 'your_DB_passwd'
mysql_host = 'your_DB_IP'

# ----------------You should have next tables in DB(mysql_host)-automations-------------
# The format is next:
# 'dev' - short name of Zabbix location; 'zabbix_auto' - corresponding table that should be present in the
# Database 'automations' on the server 'mysql_host'
zabbix_auto_tables = {'dev': 'zabbix_auto', 'staging': 'zabbix_auto_staging'}

# ----------Login & pass for login to Jira and host address----------------------------------------
jira_user = 'user'
jira_password = 'passwd'
jira_server = 'http://your_jira_url'

# -----------Pass to phantomjs module--------------------------------------------------
driver_path = "/etc/zabbix/scripts/phantomjs"

# ----------Login & pass for login to Zabbix-UI----------------------------------------
username = 'zabbix_gui_user'
password = 'zabbix_gui_passwd'
