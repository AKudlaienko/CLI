#!/usr/bin/env python3

from jira.client import JIRA
import logging
import re
import sys
import random
import datetime
from termcolor import colored, cprint
import time
import traceback
from functools import lru_cache
import json
import requests
from diskcache import Cache
import urllib3
import codecs
import string
import argparse
import inquirer
import os
import getpass
import hashlib
import base64
import string
import readline


""" some variables """
jira_server = "https://your-path-to-jira.com"
task_base_url = jira_server + "/browse/"
log_file = '/tmp/jira_cli_custom.log'
cred_file = os.environ['HOME'] + '/.jira_cli_id'

""" If you don't want ot store credentials in the file, change next line and provide your credentials."""
""" Example:
    credentials_for_jira = {"username": "test", "passwd": "123456"} """

""" If you don't know what to do, just don't touch this."""
credentials_for_jira = {}

""" Please Don't touch this block if you are not sure what you are going to do! """
""" Here you can define some additional variables. """
result_limit = 25
filter_department = ""
cache = Cache('/tmp/jira_cli_cache')
create_jira_res = ''

current_time = datetime.datetime.now().time()
time_seconds = time.time()
todayd = datetime.date.today()
date_time_now = datetime.datetime.fromtimestamp(time_seconds).strftime('%Y-%m-%d %H:%M:%S')
date = datetime.datetime.strftime(todayd, '%d.%m.%Y')
urllib3.disable_warnings()
reader = codecs.getreader("utf-8")
st_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
logging.basicConfig(format=u'%(asctime)s  %(levelname)-5s %(filename)s[LINE:%(lineno)d]  %(message)s',
                    level=logging.DEBUG, filename=u'{0}'.format(log_file))


# ------------------------------------------- Credentials ------------------------------------------------------------
def encode_cr(key, clear):
    enc = []
    for i in range(len(clear)):
        key_c = key[i % len(key)]
        enc_c = chr((ord(clear[i]) + ord(key_c)) % 256)
        enc.append(enc_c)
    return base64.urlsafe_b64encode("".join(enc).encode()).decode()


def decode_cr(key, enc):
    dec = []
    enc = base64.urlsafe_b64decode(enc).decode()
    for i in range(len(enc)):
        key_c = key[i % len(key)]
        dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
        dec.append(dec_c)
    return "".join(dec)


def credentials(credentials_f):
    if os.path.exists(credentials_f):
        if os.access(credentials_f, os.R_OK) and os.access(credentials_f, os.W_OK):
            try:
                credentials_data = json.loads(open(credentials_f).read())
                if not credentials_data:
                    print(colored("\nIt seems you file with credentials is corrupted."
                                  "\nPlease remove it and start script again.\n\n'rm -fv {}'".format(credentials_f)), 'red')
                    raise SystemExit(2)
                elif "username" and "passwd" and "user_id" not in credentials_data:
                    print(colored("\nIt seems you file with credentials is corrupted."
                                  "\nPlease remove it and start script again.\n\n'rm -fv {}'".format(credentials_f)), 'red')
                    raise SystemExit(2)

                elif credentials_data and len(credentials_data['username']) < 2:
                    print(colored("\nIt seems you 'username' or 'passwd' is empty."
                                  "\nPlease remove '{0}' and start script again.\n\n'rm -fv {0}'".format(credentials_f)), 'red')
                    raise SystemExit(2)
                cred_passwd_res = decode_cr(credentials_data["user_id"][:-1], credentials_data["passwd"])
                plain_cred = {"username": credentials_data['username'], "passwd": cred_passwd_res}
            except Exception:
                print("\nCan't get credentials from the file: {}.\nNeed to update it:".format(credentials_f))
                cred_name = input(colored("\nPlease enter 'username': ", 'red'))
                if cred_name is None or len(cred_name) < 2:
                    print("\nYou provided empty username or username with length less than 2 characters!")
                    raise SystemExit(2)
                cred_passwd = hashlib.sha256(getpass.getpass("\nPlease enter 'username': ").encode('utf-8')).hexdigest()
                plain_cred = {"username": cred_name, "passwd": cred_passwd}
                try:
                    cred_passwd_res = encode_cr(st_key + "!", cred_passwd)
                    credentials_data = {"username": cred_name, "passwd": cred_passwd_res, "user_id": st_key + "!"}
                    with open(credentials_f, 'w') as credentials_f_w:
                        credentials_f_w.write(json.dumps(credentials_data))
                except Exception:
                    sys.exit("Can't write to the file: {}!\nPlease check permissions.".format(credentials_f))
                print('\nCredentials safely stored.\n')
        else:
            print(colored("\nIssue with permissions to the file: {}".format(credentials_f), 'red'))
            raise SystemExit(2)
    else:
        print(colored("\n - It seems you don't have file with credentials - "))
        cred_name = input(colored("\nPlease enter 'username': ", 'red'))
        if cred_name is None or len(cred_name) < 2:
            print("\nYou provided empty username or username with length less than 2 characters!")
            raise SystemExit(2)
        cred_passwd = getpass.getpass("\nPlease enter 'password': ")
        if cred_name is None or len(cred_name) < 4:
            print("\nYou provided empty password or password with length less than 4 characters!")
            raise SystemExit(2)
        try:
            cred_passwd_res = encode_cr(st_key + "!", cred_passwd)
            credentials_data = {"username": cred_name, "passwd": cred_passwd_res, "user_id": st_key + "!"}
            with open(credentials_f, 'w') as credentials_f_w:
                credentials_f_w.write(json.dumps(credentials_data))
            plain_cred = {"username": cred_name, "passwd": cred_passwd}
        except Exception:
            sys.exit("Can't write to the file: {}!\nPlease check permissions.".format(credentials_f))

        print('\nCredentials safely stored.\n')
    return plain_cred


if len(credentials_for_jira) < 2 or type(credentials_for_jira) is not dict:
    logging.info("Credentials were not provided in script. Trying to find corresponding info in the file.")
    credentials_for_jira = credentials(cred_file)

try:
    jira_options = {'server': jira_server}
    jira = JIRA(options=jira_options, basic_auth=(credentials_for_jira['username'], credentials_for_jira['passwd']),
                timeout=15)

    accept_list_w = ["Roger that", "Got it", "Go ahead", "Accepted", "Well done", "Saved"]
except requests.ReadTimeout:
    print("\nConnection timeout to JIRA was reached! Please check if it reachable.")
    logging.critical("Connection timeout to JIRA was reached! Please check if it reachable.")
    raise SystemExit(2)
except Exception:
    print("Exception:\n{}".format(traceback.format_exc()))
    logging.critical("Exception:\n{}".format(traceback.format_exc()))
    raise SystemExit(2)

supported_operators = {}
required_fields_d = {}
non_required_fields_d = {}

try:
    response = requests.get(jira_server + "/rest/api/2/jql/autocompletedata", auth=(credentials_for_jira['username'],
                                                                                    credentials_for_jira['passwd']),
                            verify=False)
    if not response.status_code == 200 and not response.status_code == 400:
        logging.critical(503, "Unable to get search URL, response Code: " + str(response.status_code))
        print(503, "Unable to get search URL, response Code: " + str(response.status_code))
        raise SystemExit(2)
    raw_data = json.loads((response.content).decode('utf-8'))
    if response.status_code == 400:
        logging.critical(503, "Unable to get search URL, response Code: " + str(response.status_code) + "<br>" + raw_data["errorMessages"][0])
        print(503, "Unable to get search URL, response Code: " + str(response.status_code) + "<br>" + raw_data["errorMessages"][0])
        raise SystemExit(2)
    for i in raw_data['visibleFieldNames']:
        if 'cfid' in i:
            supported_operators.update({str(i['cfid']).strip('cf[]'): i['operators']})
        else:
            supported_operators.update({i['value']: i['operators']})

except Exception:
    print(traceback.format_exc())
    logging.error(traceback.format_exc())
    raise SystemExit(2)


# ------------------------------------ Gathering arguments ------------------------------------------------------------
def get_arguments_auto():
    if len(sys.argv) > 1:
        try:
            arg_parser = argparse.ArgumentParser(description='JIRA custom CLI',
                                                 usage='\n{0} --auto --project_id "GMM" --issuetype "task" ....\n\n'
                                                       'To get HELP for specific PROJECT:\n{0} --auto --h '
                                                       '--project_id "GMM" --issuetype "task"\n'.format(sys.argv[0]))
            arg_parser.add_argument('--auto', action='store_false', dest='mode', help='')
            arg_parser.add_argument('--h', action='store_false', dest='h', help='for help')
            arg_parser.add_argument('--project_id', action='store', dest='project_id', help='project ID in JIRA')
            arg_parser.add_argument('--ticket_id', action='store', dest='ticket_id', help='ticket ID in JIRA')
            arg_parser.add_argument('--field_id', action='store', dest='field_id', help='ID of specific field in JIRA')
            arg_parser.add_argument('--field_value', action='store', dest='field_value',
                                    help='value of specific field in JIRA - (--field_id)')
            arg_parser.add_argument('--comparative_operator', action='store', dest='comparative_operator',
                                    help="Special comparative operators. In most cases they are unique in different Project")
            arg_parser.add_argument('--summary', action='store', dest='summary', help="task's summary")
            arg_parser.add_argument('--issuetype', action='store', dest='issuetype', help="task's issue type")
            arg_parser.add_argument('--description', action='store', dest='description', help="description of the issue")
            arg_parser.add_argument('--attachment', action='store', dest='attachment',
                                    help="some attachment, (full path to the file)")
            arg_parser.add_argument('--transition', action='store', dest='transition_value',
                                    help="Done/Closed/In Progress/etc...")
            arg_parser.add_argument('--jira_assignee', action='store', dest='assignee_v', help="assignee, username from JIRA like c_ahogwarts")
            arg_parser.add_argument('--jira_reporter', action='store', dest='reporter_v', help="reporter username from JIRA like c_ahogwarts")
            #arg_parser.add_argument('--subtask', action='store', dest='subtask',
            #                        help="If '--subtask yes' - subtask will be created")
            # Here we can replace --subtask "yes" with --issuetype "Sub-task"

            all_args_raw = arg_parser.parse_args()
            if "--h" in sys.argv[2]:
                if ({'project_id', 'issuetype'} <= set(vars(all_args_raw))) and \
                        ((vars(all_args_raw)['issuetype'] != '' and vars(all_args_raw)['issuetype'] is not None)
                         and (vars(all_args_raw)['project_id'] != '' and vars(all_args_raw)['project_id'] is not None)):
                    possible_fields_raw = jira.createmeta(str(vars(all_args_raw)['project_id']).strip('"\\'),
                                                          issuetypeNames=str(vars(all_args_raw)['issuetype'])
                                                          .strip('", \\'), expand='projects.issuetypes.fields')
                    possible_fields = possible_fields_raw["projects"][0]["issuetypes"][0]["fields"]
                    print("\nHere is a list of ", colored("Required", color='red'),
                          " and ", colored("Optional", color='cyan'), " fields for specific PROJECT and Issue Type:\n")
                    for t, n in possible_fields.items():
                        if n['required'] is True or t == 'description':
                            print(colored("{0} -- {1} --> required".format(t, n['name']), color='red'))
                        else:
                            print(colored("{0} -- {1}".format(t, n['name']), color='cyan'))
                    raise SystemExit(0)

                else:
                    print("\n-- ATTENTION --\n\nIf you want to get real help for 'auto' mode, please execute command like this one:"
                          "\n{} --auto --h --project_id 'GMM' --issuetype 'task'\n".format(sys.argv[0]))
                    raise SystemExit(0)
            else:
                if {'project_id', 'issuetype'} <= set(vars(all_args_raw)):
                    if vars(all_args_raw)['project_id'] != '' and vars(all_args_raw)['project_id'] is not None:
                        if vars(all_args_raw)['issuetype'] != '' and vars(all_args_raw)['issuetype'] is not None:
                            possible_fields_raw = jira.createmeta(str(vars(all_args_raw)['project_id']).strip('"\\'),
                                                                  issuetypeNames=str(vars(all_args_raw)['issuetype'])
                                                                  .strip('", \\'), expand='projects.issuetypes.fields')
                            possible_fields = possible_fields_raw["projects"][0]["issuetypes"][0]["fields"]
                            for arg in possible_fields:
                                if arg not in vars(all_args_raw):
                                    arg_parser.add_argument('--{}'.format(arg), action='store', dest='{}'.format(arg), help='{}'
                                                            .format(possible_fields[arg]["name"]))
                        else:
                            print("\nAn argument -- 'issuetype' has an empty value.\n"
                                  "That's why I can't get ALL possible fields for this Project and Issue Type")
                            logging.error("An argument -- 'issuetype' has empty value. That's why I can't get ALL possible fields "
                                          "for this Project and Issue Type")
                            raise SystemExit(2)
            return arg_parser.parse_args()
        except Exception:
            print("Failed during gathering ARGS.\n{}".format(traceback.format_exc()))
            logging.critical("Failed during gathering ARGS. Exception:")
            logging.critical(traceback.format_exc())
            raise SystemExit(2)

# ------------------------------------ Coloring console ------------------------------------------------------------
def colored_status(issue_status):
    if re.match('Open|Backlog|Reopened', issue_status, re.IGNORECASE):
        cprint(issue_status, 'white', 'on_blue', attrs=['bold'])
    elif re.match('In Progress|Waiting For External|In Code Review X', issue_status, re.IGNORECASE):
        cprint(issue_status, 'white', 'on_yellow', attrs=['bold'])
    elif re.match('Resolved|Closed|Done|Cancelled', issue_status, re.IGNORECASE):
        cprint(issue_status, 'white', 'on_green', attrs=['bold'])
    else:
        print(issue_status)


@lru_cache(maxsize=256)
def check_fields(j_id):
    try:
        opened_task = jira.issue(j_id)
        for field_name in opened_task.raw['fields']:
            print("\nField:", field_name, "Value:", opened_task.raw['fields'][field_name])
    except Exception as o_j_ex:
        print(o_j_ex)
        print(traceback.format_exc())
        raise SystemExit(2)


# ------------------------------------Transition task -----------------------------------------------------------------
resolutions = jira.resolutions()


def transition_jira(opened_jira, resolution_value, commment):
    try:
        new_status_dict = {}
        resolutions_dict = {}
        issue = jira.issue(opened_jira)
        transitions = jira.transitions(issue)
        for r in resolutions:
            resolutions_dict.update({r.name: r.id})
        tr = '5'
        ttr = None
        for t in transitions:
            if re.search("Resolve|Closed", t['name'], re.IGNORECASE):
                tr = t['id']
                break
            elif re.match("Start", t['name'], re.IGNORECASE):
                tr = t['id']
                transitions_sec = jira.transitions(issue)
                for tt in transitions_sec:
                    if re.match("Resolve|Closed", tt['name'], re.IGNORECASE):
                        ttr = tt['id']
                        break
                break
            else:
                continue
        logging.info("Trying to transition issue...")
        if ttr is None:
            print(resolution_value)
            print(resolutions_dict["{}".format(resolution_value)])
            jira.transition_issue(opened_jira, int(tr),
                                  fields={'assignee': {'name': "{}".format(credentials_for_jira['username'])},
                                          'resolution': {'id': resolutions_dict["{}".format(resolution_value)]}}, comment=commment)
            return resolution_value
        else:
            jira.transition_issue(opened_jira, int(tr))
            jira.transition_issue(opened_jira, int(ttr),
                                  fields={'assignee': {'name': "{}".format(credentials_for_jira['username'])},
                                          'resolution': {'id': resolutions_dict["{}".format(resolution_value)]}}, comment=commment)
            return resolution_value
    except Exception:
        logging.error("Crashed while transition jira-issue!")
        logging.error(traceback.format_exc())
        print("\nCrashed while transition jira-issue!\nException:{0}".format(traceback.format_exc()))
        raise SystemExit(2)


""" --- JiraCli class --- """


class JiraCli(object):

    def __init__(self, all_arguments_raw):
        self.all_arguments_raw = all_arguments_raw

    @lru_cache(maxsize=256)
    def get_j_projects(self, opt):
        try:
            projects = jira.projects()
            j_proj_exist = {}
            j_proj_exist_keys = []
            for i in projects:
                j_proj_exist.update({i.key: i.name})
            if opt == 'j_print':
                for key, name in j_proj_exist.items():
                    print(colored(key, 'red'), colored(" - {}".format(name), 'green'))
            else:
                for key in j_proj_exist.keys():
                    j_proj_exist_keys.append(key)
                return sorted(j_proj_exist_keys)
        except Exception as o_j_ex:
            print(o_j_ex)
            print(traceback.format_exc())
            raise SystemExit(2)

    @lru_cache(maxsize=256)
    def j_project_data(self, j_id):
        proj_data = jira.project(j_id)
        return proj_data

    def checkboxes(self, question, choices_list):
            questions = [inquirer.Checkbox('value', message="{}".format(question),
                                           choices=choices_list,)]
            """ returns a dict """
            answers = inquirer.prompt(questions)
            return answers['value']

    def check_option(self, question, choices_list):
        questions = [inquirer.List('option', message="{}".format(question), choices=choices_list,),]
        answer = inquirer.prompt(questions)
        return answer['option']

    def one_by_one(self, a):
        allowedValues_lst = []
        for i in a["allowedValues"]:
            if "value" in i.keys():
                allowedValues_lst.append(i["value"])
            elif "name" in i.keys():
                allowedValues_lst.append(i["name"])
        return allowedValues_lst

    def gather_required_fields(self, data_dictionary, type):
        global required_fields_d
        global non_required_fields_d
        non_required_fields_names = []
        for_clearing = []
        if type == "Necessary":
            s_color = 'red'
            print(colored("{} fields for this project are:\n".format(type), 'green',
                          attrs=['bold']))
            for req_key in data_dictionary:
                if not isinstance(data_dictionary[req_key], str):
                    if data_dictionary[req_key]["required"] is True or req_key == "description":
                        print(colored("-{}-   ".format(data_dictionary[req_key]["name"]),
                                      '{}'.format(s_color)), end="")
                        if "allowedValues" in data_dictionary[req_key]:
                            required_fields_d.update({req_key: {"name": data_dictionary[req_key]["name"],
                                                                "allowedValues": data_dictionary[req_key]["allowedValues"]}})
                        else:
                            required_fields_d.update({"{}".format(req_key): {"name": "{}".format(data_dictionary[req_key]["name"])}})

        else:
            for req_key in data_dictionary:
                if not isinstance(data_dictionary[req_key], str):
                    if data_dictionary[req_key]["required"] is False and req_key != "description":
                        non_required_fields_names.append(data_dictionary[req_key]["name"])
                        if "allowedValues" in data_dictionary[req_key]:
                            non_required_fields_d.update({req_key: {"name": data_dictionary[req_key]["name"],
                                                      "allowedValues": data_dictionary[req_key]["allowedValues"]}})
                        else:
                            non_required_fields_d.update({req_key: {"name": data_dictionary[req_key]["name"]}})
            print(colored("\n\nAttention !!!\nSelect only fields you want to declare and  don't leave fields empty!\n",
                          'yellow', attrs=['bold']))
            answers_non_required_fields_names = self.checkboxes("Please choose {} fields. Use space to mark".format(type),
                                                                non_required_fields_names)
            for k, v in non_required_fields_d.items():
                if v["name"] not in answers_non_required_fields_names:
                    for_clearing.append(k)
            for d in for_clearing:
                non_required_fields_d.pop(d, None)

    def desc_input(self, field_name):
        print(colored("Please enter {}.\nPress Ctrl-D to save it.".format(field_name), 'yellow', attrs=['bold']))
        while True:
            try:
                line = input()
            except EOFError:
                break
            content = ''.join(line)
            yield content

    def enter_required_data(self, req_field, type):
        if "allowedValues" in req_field.keys() and len(self.one_by_one(req_field)) >= 1:
            j_field = self.check_option("{} - choose from possible values".format(req_field["name"]),
                                        self.one_by_one(req_field))
            print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
            for item in req_field['allowedValues']:
                if 'value' in item:
                    if j_field in item['value']:
                        j_field_f = {'value': j_field}
                        yield j_field_f
                    else:
                        continue
                elif 'name' in item:
                    if j_field in item['name']:
                        j_field_f = {'name': j_field}
                        yield j_field_f
                    else:
                        continue
        else:
            for k in range(2):
                if re.match("Description", req_field["name"], re.IGNORECASE):
                    j_field = ''.join(self.desc_input(req_field["name"]))
                else:
                    j_field = input(colored("\nPlease enter '{}': ".format(req_field["name"]), 'yellow'))
                if type == 'required' and len(j_field) >= 1 and j_field:
                    print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                    yield j_field
                elif type != 'required':
                    print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                    yield j_field
                elif len(j_field) < 1 and k != 1:
                    print(colored(
                        "You can't create task without {0}.\nPlease provide {0}, at least 1+ character.".format(req_field["name"]),
                        'red', attrs=['bold']))
                    continue
                elif k == 1:
                    print("You've missed again. Read output above attentively!")
                    raise SystemExit(2)
                break

    def upd_req_data(self, req_f, req_data, type):

        for r_f_k in req_f:
            req_field_data = self.enter_required_data(req_f[r_f_k], type)

            if r_f_k == 'project' or r_f_k == 'issuetype':
                continue
            elif r_f_k == 'reporter' or r_f_k == 'assignee':
                self.enter_required_data(req_f[r_f_k], type)
                for i in req_field_data:
                    req_data.update({r_f_k: {"name": i}})
            else:
                self.enter_required_data(req_f[r_f_k], type)
                for i in req_field_data:
                    req_data.update({r_f_k: i})
        return req_data

    def get_issue(self, ID):
        issue = jira.search_issues(ID)
        print(issue)

    # --------------------------- search_existing tasks ---------------------------------------------------------------
    def search_opened(self, project_jira, custom_filed_id, some_value, comparative_operator):
        """This function searches jira-tikets by. Next arguments needed:
        1 - Project key like: PROJ-key - "STL"
        2 - Field-ID like: "Status decription" - 13836
        3 - Some value to compare with, example: `cf[13836] = "fixed"` (JQL Syntax!)
        4 - corresponding `comparative_operator` should be chosen, otherwise you may get unexpected consequences! """

        try:
            if comparative_operator in supported_operators[custom_filed_id]:
                if str.isdigit(custom_filed_id):
                    custom_filed_id = int(custom_filed_id)
                    search_result = (jira.search_issues('project = "{0}" AND cf[{1}] {3} "{2}"'
                                                        .format(project_jira, custom_filed_id, some_value,
                                                                comparative_operator), maxResults=10, expand=True))
                else:
                    search_result = (jira.search_issues('project = "{0}" AND {1} {3} "{2}"'
                                                        .format(project_jira, custom_filed_id, some_value,
                                                                comparative_operator), maxResults=10, expand=True))
                    print(search_result)
                search_result_list = []
                for i in search_result:
                    search_result_list.append(i.key)
                return search_result_list
            else:
                logging.error(
                    "Wrong OPERATOR. Supported comparative operators: {}".format(supported_operators[custom_filed_id]))
                print("\nError: Wrong OPERATOR!\nSupported comparative operators for field/field-ID '{0}': {1}"
                      .format(custom_filed_id, supported_operators[custom_filed_id]))
                raise SystemExit(2)
        except Exception as check_opened_ex:
            logging.error("Can't fetch corresponding info concerning task. Exception: {}".format(check_opened_ex))
            logging.error(traceback.format_exc())

    def opened_issue(self, project_key, custom_filed_id, some_value, comparative_operator):
        try:
            raw_list = self.search_opened(project_key, custom_filed_id, some_value, comparative_operator)
            if raw_list is not None and len(raw_list) == 1:
                return raw_list[0]
            elif raw_list and len(raw_list) > 1:
                print("Got couple tasks. Don't know which one is correct!\nList: {}".format(raw_list))
                logging.error("Got couple tasks. Don't know which one is correct!\nList: {}".format(raw_list))
                raise SystemExit(2)
            elif raw_list is None or len(raw_list) == 0:
                return None
        except Exception:
            print("Failed during fetching opened_task_ID. Func: opened_issue()")
            print(traceback.format_exc())
            logging.error("Failed during fetching opened_task_ID. Func: opened_issue()\nException: {}"
                          .format(traceback.format_exc()))
            raise SystemExit(2)

    # ------------------------------------Get last comment ------------------------------------------------------------
    @lru_cache(maxsize=256)
    def get_last_comment(self, opened_jira):
        all_comments = jira.comments(opened_jira)
        return {"author": all_comments[-1].author.displayName, "body": all_comments[-1].body,
                "created": all_comments[-1].created}

    # -------------------------------------- Create/Update JIRA task --------------------------------------------------
    def create_jira(self):
        if self.all_arguments_raw and self.all_arguments_raw is not None:
            if self.all_arguments_raw.project_id and self.all_arguments_raw.project_id != '':
                if self.all_arguments_raw.ticket_id and self.all_arguments_raw.ticket_id != "":
                    opened_jira = self.all_arguments_raw.ticket_id
                else:
                    opened_jira = self.opened_issue(self.all_arguments_raw.project_id, self.all_arguments_raw.field_id,
                                                    self.all_arguments_raw.field_value,
                                                    self.all_arguments_raw.comparative_operator)
                try:
                    issue_dict = {
                        'project': self.all_arguments_raw.project_id,
                        'summary': """{}""".format(self.all_arguments_raw.summary),
                        'description': """{}""".format(self.all_arguments_raw.description),
                        'issuetype': {'name': '{}'.format(self.all_arguments_raw.issuetype)},
                    }
                    if self.all_arguments_raw.reporter_v and len(self.all_arguments_raw.reporter_v) > 2:
                        issue_dict.update({'reporter': {'name': self.all_arguments_raw.reporter_v}})
                    if self.all_arguments_raw.assignee_v and len(self.all_arguments_raw.assignee_v) > 2:
                        issue_dict.update({'assignee': {'name': self.all_arguments_raw.assignee_v}})
                    if opened_jira != 'new' and opened_jira != "*****":
                        try:
                            prev_issue = jira.issue(opened_jira)
                            prev_issue_status = prev_issue.fields.status
                            if re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE) \
                                    and (self.all_arguments_raw.issuetype != 'Sub-task'):
                                logging.info("Creating new JIRA")
                                new_jira = jira.create_issue(fields=issue_dict)
                                if self.all_arguments_raw.attachment and self.all_arguments_raw.attachment != '':
                                    with open(self.all_arguments_raw.attachment, 'rb') as f:
                                        jira.add_attachment(issue=new_jira, attachment=f)
                                j_k = new_jira.key
                                jira_link = "{0}{1}".format(task_base_url, j_k)
                                logging.info("Task: {0} was created.".format(j_k))
                                print(jira_link)
                                create_jira_res = 'created'
                            elif not re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE) \
                                    and (self.all_arguments_raw.issuetype == 'Sub-task'):
                                try:
                                    issue_dict = {
                                        'project': self.all_arguments_raw.project_id,
                                        'summary': """{}""".format(self.all_arguments_raw.summary),
                                        'description': """{}""".format(self.all_arguments_raw.description),
                                        'issuetype': {'name': 'Sub-task'},
                                        'parent': {'id': '{}'.format(opened_jira)},
                                    }
                                    sub_task = jira.create_issue(fields=issue_dict)
                                    if self.all_arguments_raw.attachment and self.all_arguments_raw.attachment != '':
                                        with open(self.all_arguments_raw.attachment, 'rb') as f:
                                            jira.add_attachment(issue=sub_task, attachment=f)
                                    sub_k = sub_task.key
                                    jira_link = "{0}{1}".format(task_base_url, sub_k)
                                    logging.info("Subtask: {0} was created.".format(sub_k))
                                    print(jira_link)
                                    create_jira_res = 'subtask created'
                                except Exception:
                                    logging.error("SubTask was not created ! Exception:")
                                    logging.error(traceback.format_exc())
                                    create_jira_res = 'subtask failed'
                            elif not re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE) \
                                    and (self.all_arguments_raw.transition_value is not None and len(self.all_arguments_raw.transition_value) >= 3):
                                    transition_jira_res = transition_jira(opened_jira, self.all_arguments_raw.transition_value, self.all_arguments_raw.description)
                                    logging.info("Task: {0} has got state: {1}.".format(opened_jira, transition_jira_res))
                                    create_jira_res = 'updated'
                            elif not re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE) \
                                    and (self.all_arguments_raw.assignee_v != '' or self.all_arguments_raw.reporter_v != ''):

                                if self.all_arguments_raw.assignee_v != '' and len(self.all_arguments_raw.assignee_v) > 2:
                                    upd_fields = {'name': self.all_arguments_raw.assignee_v}
                                    prev_issue.update(assignee=upd_fields)
                                    create_jira_res = 'reassigned'
                                else:
                                    logging.error("Task was not reassigned ! Exception:")
                                    logging.error(traceback.format_exc())
                                    raise SystemExit(2)

                                if self.all_arguments_raw.reporter_v != '' and len(self.all_arguments_raw.reporter_v) > 2:
                                    upd_fields = {'name': self.all_arguments_raw.reporter_v}
                                    prev_issue.update(reporter=upd_fields)
                                    create_jira_res = 'reassigned'
                                else:
                                    logging.error("Task was not reassigned ! Exception:")
                                    logging.error(traceback.format_exc())
                                    raise SystemExit(2)

                                if self.all_arguments_raw.description and len(self.all_arguments_raw.description) > 3:
                                    logging.info("I'm going to add comment to it")
                                    comment = jira.add_comment(opened_jira, 'new comment')
                                    comment.update(body=self.all_arguments_raw.description)
                                    if self.all_arguments_raw.attachment and self.all_arguments_raw.attachment != '':
                                        with open(self.all_arguments_raw.attachment, 'rb') as f:
                                            jira.add_attachment(issue=opened_jira, attachment=f)
                                    create_jira_res = 'updated'


                            else:
                                logging.info("Task: {} still not Done/Closed.".format(prev_issue))
                                logging.info("I'm going to add comment to it")
                                comment = jira.add_comment(opened_jira, 'new comment')
                                comment.update(body=self.all_arguments_raw.description)
                                if self.all_arguments_raw.attachment and self.all_arguments_raw.attachment != '':
                                    with open(self.all_arguments_raw.attachment, 'rb') as f:
                                        jira.add_attachment(issue=opened_jira, attachment=f)
                                create_jira_res = 'updated'
                        except Exception:
                            logging.error("Task was not created/updated ! Exception:")
                            logging.error(traceback.format_exc())
                            create_jira_res = 'failed'
                            raise SystemExit(2)

                    else:
                        logging.info("Creating new Task")
                        new_jira = jira.create_issue(fields=issue_dict)
                        if self.all_arguments_raw.attachment and self.all_arguments_raw.attachment != '':
                            with open(self.all_arguments_raw.attachment, 'rb') as f:
                                jira.add_attachment(issue=new_jira, attachment=f)
                        j_k = new_jira.key
                        jira_link = "{0}{1}".format(task_base_url, j_k)
                        logging.info("Task: {0} was created.".format(j_k))
                        print(jira_link)
                        create_jira_res = 'created'
                    return create_jira_res
                except Exception as con_ex:
                    logging.critical("Failed to connect to JIRA: {0}".format(con_ex))
                    logging.critical(traceback.format_exc())
                    raise SystemExit(2)
            else:
                print("Failed because --project_i was not provided.\nIt's a critical argument")
                logging.critical("Failed becuse --project_i was not provided.")
                raise SystemExit(2)
        else:
            print("It seems variable 'all_arguments_raw' is empty or was not found")
            logging.critical("It seems variable 'all_arguments_raw' is empty or was not found")
            raise SystemExit(2)


    def interactive_m(self):
        print(colored("Available JIRA projects:", 'green', attrs=['bold']))
        for a, b, c, d, e, f, g, h in zip(self.get_j_projects('')[::8], self.get_j_projects('')[1::8],
                                       self.get_j_projects('')[2::8], self.get_j_projects('')[3::8],
                                       self.get_j_projects('')[4::8], self.get_j_projects('')[5::8],
                                       self.get_j_projects('')[6::8], self.get_j_projects('')[7::8]):
            print('{:<15}{:<15}{:<15}{:<15}{:<15}{:<15}{:<15}{:<}'.format(a, b, c, d, e, f, g, h))
        for p in range(2):
            j_project = input(colored("\nPlease enter PROJECT ID: ", 'yellow'))
            if j_project is not None and j_project in self.get_j_projects(''):
                print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                issue_types_r = self.j_project_data(j_project).issueTypes
                issue_types = []
                required_data = {}
                for i_t in issue_types_r:
                    issue_types.append(i_t.name)
                options = ['Issue', 'SubTask']
                answer = self.check_option("What would you like to create", options)
                print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                if answer == "SubTask":
                    for count_t_id in range(2):
                        t_id = input(colored("\nPlease enter ticket ID: ", 'yellow'))
                        if count_t_id < 1 and (t_id is None or len(t_id) < 3):
                            print(colored('Please provide correct ticket-ID like: ', 'red'), 'GMM-34934')
                            continue
                        elif count_t_id == 1 and (t_id is None or len(t_id) < 3):
                            print("\nThe value you've entered: '{}', is not allowed.".format(t_id))
                            print("You've missed again. Read output above attentively!")
                            raise SystemExit(2)
                        else:
                            subtask_upd_create = self.check_option("Do you want to CREATE new, UPDATE or CLOSE SubTask?",
                                                                   ['new', 'update', 'close'])
                            print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                            if subtask_upd_create == 'new':
                                try:
                                    chek_issue_res = jira.issue(t_id)
                                    logging.info("{}".format(chek_issue_res))
                                    for t_s in range(2):
                                        t_summary = input(colored("\nPlease provide summary: ", 'yellow'))
                                        if (not t_summary or len(t_summary) < 3) and t_s != 1:
                                            print(colored("You can't create/update this issue with an empty summary. Mim 3 symbols!", 'red'))
                                            continue
                                        elif (not t_summary or len(t_summary) < 3) and t_s == 1:
                                            print("You've missed again. Read output above attentively!")
                                            raise SystemExit(2)
                                        else:
                                            t_description = ''.join(self.desc_input("Description"))
                                            print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                                            t_attachment = input(colored("\nIf you want to attach some file, "
                                                                         "please provide full path to the file: ", 'yellow'))
                                            print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                                            try:
                                                issue_dict = {
                                                    'project': j_project,
                                                    'summary': """{}""".format(t_summary),
                                                    'description': """{}""".format(t_description),
                                                    'issuetype': {'name': 'Sub-task'},
                                                    'parent': {'id': '{}'.format(t_id)},
                                                }
                                                sub_task = jira.create_issue(fields=issue_dict)
                                                if t_attachment and t_attachment != '':
                                                    with open(t_attachment, 'rb') as f:
                                                        jira.add_attachment(issue=sub_task, attachment=f)
                                                sub_k = sub_task.key
                                                jira_link = "{0}{1}".format(task_base_url, sub_k)
                                                logging.info("Sub-Task: {0} was created.".format(sub_k))
                                                print(colored("\nSub-Task was created: ", 'magenta', attrs=['bold']),
                                                      "{}".format(jira_link))
                                                create_jira_res = 'subtask created'
                                                return create_jira_res
                                            except Exception:
                                                logging.error("SubTask was not created ! Exception:")
                                                logging.error(traceback.format_exc())
                                                raise SystemExit(2)
                                except Exception:
                                    print("It seems there is no Task: {} or maybe I have no permissions ?!".format(t_id))
                                    logging.critical("It seems there is no Task: {} or maybe I have no permissions ?!"
                                                     .format(t_id))
                                    raise SystemExit(2)
                            elif subtask_upd_create == 'update' or subtask_upd_create == 'close':
                                try:
                                    prev_issue = jira.issue(t_id)
                                    prev_issue_status = prev_issue.fields.status
                                    if re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE):
                                        print(colored("\nHey, this Sub-Task - {} is closed!\n"
                                                      .format(t_id), 'red'))
                                        raise SystemExit(0)
                                    elif not re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE) \
                                            and subtask_upd_create == 'close':
                                        """ - Ask to choose resolution
                                            - Ask to enter comment/root cause"""
                                        resolution_v = self.check_option("Please choose the resolution:", resolutions)
                                        comment_field = ''.join(self.desc_input("comment/root cause"))
                                        for count_t_id_2 in range(2):
                                            if count_t_id_2 < 1 and (comment_field is None or len(comment_field) < 3):
                                                print("Please provide at least 3 characters")
                                                continue
                                            elif count_t_id_2 == 1 and (
                                                    comment_field is None or len(comment_field) < 3):
                                                print("You've missed again. Read output above attentively!")
                                                raise SystemExit(2)
                                            else:
                                                break
                                        answer_for_creation = input(colored("\nDo you really want to Close/Resolve it?"
                                                                            " [Yes|No]: ", 'red',
                                                                            'on_white', attrs=['bold']))
                                        if answer_for_creation and re.search('yes|Y', answer_for_creation,
                                                                             re.IGNORECASE):
                                            transition_jira(t_id, resolution_v, comment_field)
                                            print(colored("OK. Resolving issue...", 'green', attrs=['bold']))
                                            raise SystemExit(0)
                                        else:
                                            print("\nYour have answered: ", colored(answer_for_creation, color='red',
                                                                                    attrs='bold'), "\nBye")
                                            raise SystemExit(0)
                                    else:
                                        comment_field = input(colored("\nPlease enter your comment: ", 'yellow'))
                                        for count_t_id_2 in range(2):
                                            if count_t_id_2 < 1 and (comment_field is None or len(comment_field) < 3):
                                                print("Please provide at least 3 characters")
                                                continue
                                            elif count_t_id_2 == 1 and (comment_field is None or len(comment_field) < 3):
                                                print("You've missed again. Read output above attentively!")
                                                raise SystemExit(2)
                                            else:
                                                break

                                        attach_file = input(colored("\nIf you have attachment, please provide full path"
                                                                " to the file: ", 'yellow'))
                                        answer_for_creation = input(colored("\nDo you really want to create/update it?"
                                                                            " [Yes|No]: ", 'red',
                                                                            'on_white', attrs=['bold']))
                                        if answer_for_creation and re.search('yes|Y', answer_for_creation,
                                                                             re.IGNORECASE):
                                            print(colored("OK. Updating issue...", 'green', attrs=['bold']))
                                            comment = jira.add_comment(t_id, 'New Sub-Task update')
                                            comment.update(body=comment_field)
                                            if attach_file and attach_file != '':
                                                with open(attach_file, 'rb') as f:
                                                    jira.add_attachment(issue=t_id, attachment=f)
                                            print(colored("\nSub-Task was updated:", 'magenta', attrs=['bold']),
                                                  "{0}{1}".format(task_base_url, t_id))
                                            create_jira_res = 'updated'
                                            return create_jira_res
                                        else:
                                            print("\nYour have answered: ", colored(answer_for_creation, color='red',
                                                                                    attrs='bold'), "\nBye")
                                            raise SystemExit(0)
                                except Exception as prev_issue_upd:
                                    print("Error: {0}.\nExcepption:{1}\n".format(prev_issue_upd, traceback.format_exc()))
                                    logging.critical("Error: {0}.\nExcepption:{1}\n".format(prev_issue_upd,
                                                                                            traceback.format_exc()))

                else:
                    issue_upd_create = self.check_option("Do you want to CREATE new or UPDATE existing task or CLOSE the task",
                                                         ['new', 'update', 'close'])
                    print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                    if issue_upd_create == 'new':
                        issue_type_name = self.check_option("Please choose from possible Issue Types", issue_types)
                        required_fields_raw = jira.createmeta(j_project, issuetypeNames=issue_type_name,
                                                              expand='projects.issuetypes.fields')
                        required_fields = required_fields_raw["projects"][0]["issuetypes"][0]["fields"]
                        self.gather_required_fields(required_fields, "Necessary")
                        self.gather_required_fields(required_fields, "Optional")
                        required_data.update({"project": j_project, "issuetype": {'name': issue_type_name}})
                        required_data.update(self.upd_req_data(required_fields_d, required_data, 'required'))

                        required_data.update(self.upd_req_data(non_required_fields_d, required_data, 'non required'))
                        print(colored("\nPlease check if everything right:\n", 'green', attrs=['bold']))
                        for w_k, w in required_data.items():
                            if w_k == "issuetype":
                                print('{0} -- {1}'.format(required_fields[w_k]["name"], w["name"]))
                            else:
                                print('{0} -- {1}'.format(required_fields[w_k]["name"], w))
                        answer_for_creation = input(
                            colored("\nDo you really want to create/update it? [Yes|No]: ", 'red', 'on_white', attrs=['bold']))
                        if answer_for_creation and re.search('yes|Y', answer_for_creation, re.IGNORECASE):
                            print(colored("OK. Creating issue...", 'green', attrs=['bold']))
                            try:
                                if "attachment" in required_data:
                                    t_attachment = required_data.pop("attachment")
                                else:
                                    t_attachment = ''
                                new_issue = jira.create_issue(fields=required_data)
                                if t_attachment and t_attachment != '':
                                    with open(t_attachment, 'rb') as f:
                                        jira.add_attachment(issue=new_issue, attachment=f)
                                print(colored("\nTask was created:", 'magenta', attrs=['bold']),
                                      "{0}{1}".format(task_base_url, new_issue.key))
                                create_jira_res = 'created'
                                return create_jira_res
                            except Exception as t_cr_ex:
                                print(colored("\nError: {}".format(t_cr_ex), 'red'))
                                print(traceback.format_exc())
                                raise SystemExit(2)
                        else:
                            print("You've answered ", colored("'{}'. ".format(answer_for_creation), color='red',
                                                            attrs='bold'), "\nBye")
                            raise SystemExit(0)
                    elif issue_upd_create == 'update' or issue_upd_create == 'close':
                        for count_t_id in range(2):
                            t_id = input(colored("\nPlease enter ticket ID: ", 'yellow'))
                            if count_t_id < 1 and (t_id is None or len(t_id) < 3):
                                print(colored('Please provide correct ticket-ID like: ', 'red'), 'STL-34934')
                                continue
                            elif count_t_id == 1 and (t_id is None or len(t_id) < 3):
                                print("\nThe value you've entered: '{}', is not allowed.".format(t_id))
                                print("You've missed again. Read output above attentively!")
                                raise SystemExit(2)
                            else:
                                print(colored(random.choice(list(accept_list_w)), 'green', attrs=['bold']))
                                try:
                                    prev_issue = jira.issue(t_id)
                                    prev_issue_status = prev_issue.fields.status
                                    if re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE):
                                        print(colored("\nHey, this task - {} is closed!\n".format(t_id), 'red'))
                                        raise SystemExit(0)
                                    elif not re.search('Done|Closed|CANCELLED', str(prev_issue_status), re.IGNORECASE) \
                                            and issue_upd_create == 'close':
                                        """ - Ask to choose resolution
                                            - Ask to enter comment/root cause"""
                                        resolution_v = self.check_option("Please choose the resolution:", resolutions)
                                        comment_field = ''.join(self.desc_input("comment/root cause"))
                                        for count_t_id_2 in range(2):
                                            if count_t_id_2 < 1 and (comment_field is None or len(comment_field) < 3):
                                                print("Please provide at least 3 characters")
                                                continue
                                            elif count_t_id_2 == 1 and (
                                                    comment_field is None or len(comment_field) < 3):
                                                print("You've missed again. Read output above attentively!")
                                                raise SystemExit(2)
                                            else:
                                                break
                                        answer_for_creation = input(colored("\nDo you really want to Close/Resolve it?"
                                                                            " [Yes|No]: ", 'red',
                                                                            'on_white', attrs=['bold']))
                                        if answer_for_creation and re.search('yes|Y', answer_for_creation,
                                                                             re.IGNORECASE):
                                            transition_jira(t_id, resolution_v, comment_field)
                                            print(colored("OK. Resolving issue...", 'green', attrs=['bold']))
                                            raise SystemExit(0)
                                        else:
                                            print("\nYour have answered: ", colored(answer_for_creation, color='red',
                                                                               attrs='bold'), "\nBye")
                                            raise SystemExit(0)
                                    else:
                                        comment_field = input(colored("\nPlease enter your comment: ", 'yellow'))
                                        for count_t_id_2 in range(2):
                                            if count_t_id_2 < 1 and (comment_field is None or len(comment_field) < 3):
                                                print("Please provide at least 3 characters")
                                                continue
                                            elif count_t_id_2 == 1 and (comment_field is None or len(comment_field) < 3):
                                                print("You've missed again. Read output above attentively!")
                                                raise SystemExit(2)
                                            else:
                                                break

                                        attach_file = input(colored("\nIf you have attachment, please provide full path"
                                                                    " to the file: ", 'yellow'))
                                        answer_for_creation = input(colored("\nDo you really want to create/update it?"
                                                                            " [Yes|No]: ", 'red',
                                                                            'on_white', attrs=['bold']))
                                        if answer_for_creation and re.search('yes|Y', answer_for_creation,
                                                                             re.IGNORECASE):
                                            print(colored("OK. Updating issue...", 'green', attrs=['bold']))
                                            comment = jira.add_comment(t_id, 'New update')
                                            comment.update(body=comment_field)
                                            if attach_file and attach_file != '':
                                                with open(attach_file, 'rb') as f:
                                                    jira.add_attachment(issue=t_id, attachment=f)
                                            print(colored("\nTask was updated:", 'magenta', attrs=['bold']),
                                                  "{0}{1}".format(task_base_url, t_id))
                                            create_jira_res = 'updated'
                                            return create_jira_res
                                        else:
                                            print("\nYour have answered: ", colored(answer_for_creation, color='red',
                                                                                    attrs='bold'), "\nBye")
                                            raise SystemExit(0)
                                except Exception as prev_issue_upd:
                                    print("Error: {0}.\nExcepption:{1}\n".format(prev_issue_upd, traceback.format_exc()))
                                    logging.critical("Error: {0}.\nExcepption:{1}\n".format(prev_issue_upd,
                                                                                            traceback.format_exc()))
            else:
                print("Hey!\nThe value you've entered: '{}', doesn't exist.".format(j_project))
                if p == 1:
                    print("You've missed again. Read output above attentively!")
                    raise SystemExit(2)
                else:
                    print("Here are possible values:")
                    self.get_j_projects('j_print')
                    continue

# ---------------------------------------------- main ---------------------------------------------------------------


def check_mode():
    try:
        if len(sys.argv) >= 2 and 'auto' in sys.argv[1]:
            try:
                if len(sys.argv) >= 3 and sys.argv[2] != "":
                    try:
                        if sys.argv[2] == 'close' or sys.argv[2] == 'resolve':
                            try:
                                if sys.argv[3]:
                                    json_data = json.loads(sys.argv[3])
                                    print(json_data)
                                else:
                                    print("\nFailed during resolving/closing issue.\n"
                                          "Please provide corresponding data as 3-rd argument in JSON format.\n")
                                    logging.critical("Failed during resolving/closing issue. "
                                                     "Please provide corresponding data as 3-rd argument in JSON format.")
                                    raise SystemExit(2)
                            except Exception:
                                print("\nFailed during resolving/closing issue.\nException:\n{}".format(traceback.format_exc()))
                                logging.critical("Failed during resolving/closing issue. Exception:\n{}".format(traceback.format_exc()))
                                raise SystemExit(2)
                            #Probably, need to continue with function transition_jira()
                            pass

                        else:
                            t = JiraCli(get_arguments_auto())
                            t.create_jira()
                    except Exception:
                        print("\nFailed in Auto-mode.\nException:\n{}".format(traceback.format_exc()))
                        logging.critical("Failed in Auto-mode. Exception:\n{}".format(traceback.format_exc()))
                        raise SystemExit(2)
                else:
                    print("\n * Please provide corresponding arguments\n")
                    print("\n * If you want to Close/Resolve ticket, please put '--close yes'\n")
                    logging.critical("Please provide corresponding ARGS")
                    raise SystemExit(2)
            except IndexError:
                print('\nUsage:\n', colored('- AUTO-mode:', 'yellow'),
                      '\n %s  --auto --project_id "STL" --ticket_id "STL-32" --issuetype "Sub-task" --summary "TEST"'
                      '--description "Some test description"\n' % sys.argv[0])
        elif len(sys.argv) == 1:
            t = JiraCli(get_arguments_auto())
            t.interactive_m()
        else:
            print('\nUsage:\n', colored('- AUTO-mode:', 'yellow'), '\n %s --auto --project_id "ATLAS" --issuetype "Sub-task" --ticket_id "ATLAS-42323" --summary "34234234" --description "see attachment"  --attachment "/tmp/some_logs.log"\n' % sys.argv[0])
            print(colored('- Interactive mode:', 'yellow'), '\n Just start without any arguments: %s' % sys.argv[0])
    except Exception:
        print(colored("Exception:\n", 'red'), '{}'.format(traceback.format_exc()))
        raise SystemExit(2)


if __name__ == "__main__":
   check_mode()
