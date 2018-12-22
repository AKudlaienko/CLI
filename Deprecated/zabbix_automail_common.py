#!/usr/bin/env python3

# ATTENTION !!!
# You should test script manually before add to automation tool !
from pyzabbix import ZabbixAPI, ZabbixAPIException
import re
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import requests
import pickle
from random import randint
import datetime
import time
import smtplib
from email.mime.text import MITeamText
from email.mime.image import MITeamImage
from email.mime.multipart import MITeamMultipart
from email.utils import make_msgid
import os
import mysql.connector as mariadb
from mysql.connector import errorcode
from jira.client import JIRA
import logging
import json
from loginn_info import *



keyword = 'TAGS'
logging.basicConfig(format=u'%(asctime)s  %(levelname)-5s %(filename)s[LINE:%(lineno)d]  %(message)s', level=logging.INFO, filename=u'{0}'.format(log_file))
current_time = datetime.datetime.now().time()
time_seconds = time.time()
todayd = datetime.date.today()
date_time_now = datetime.datetime.fromtimestamp(time_seconds).strftime('%Y-%m-%d %H:%M:%S')
date = datetime.datetime.strftime(todayd, '%d.%m.%Y')
res_email_sent = 0
cc_recipients = []

# --------------------------------------------------------------------------------------------


def main(zabbix_location):

    logging.info(">>>>>  ZABBIX - {0} <<<<<<< ".format(zabbix_location))
    logging.info("...............................................................................................")
    web_url = zabbix_hosts[zabbix_location]
    me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + str('Zabbix check error') + str(zabbix_location)
# -------------------------------------------------------------------------------------------
    if (current_time > from_time) or (current_time < to_time):
        logging.info("Time now is {0}. To prevent false alerts I'm going to sleep until {1}".format(current_time, to_time))
        raise SystemExit(0)
# ---------------------------- email to Team --------------------------------------------------
    def email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log):
        try:
            msg = MITeamText(msg_me, 'html')
            msg['Subject'] = me_mail_subject
            msg['From'] = 'nocteam@test.com'
            msg['To'] = "MONITORING@test.com"
            send = smtplib.SMTP(mail_server_address)
            send.send_message(msg)
            send.close()
            logging.critical("Troubles with INCIDENT-email sending - {0}".format(msg_log))
            logging.info("So I've sent corresponding email tom Team")
        except Exception as me:
            global id
            if id:
                logging.error("email_to_me was not sent. Exception:{0}. Id-{1}".format(me, id))
            else:
                logging.error("email_to_me was not sent. Exception: {0}. Subject - {1}".format(me, me_mail_subject))

# -----------------------------------------------------------------------------------
    def parce_recipients(recipients_string):
        result = re.sub('\s+|\n|;|,|\t', ' ', recipients_string).split(' ')
        return result
# ----------------------- Convert time to Zabbix_time --------------------------------

    def convert_time(graph_time_range_string):
        if graph_time_range_string:
            global num_args
            num_args = len(re.split(';|,|\n |\t', graph_time_range_string))
            try:
                logging.info("I'm converting graph_time_range_string")
                time_dict = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
                global time_val_dict
                time_val_dict = {}
                raw_time_g = re.split('(\d+)', graph_time_range_string)
                raw_time_g.remove('')
                t_list_len = len(raw_time_g) - 1
                tt = 1
                for t in range(t_list_len):
                    if t % 2 == 0:
                        t_time_value = raw_time_g[t]
                        t_time_marker_raw = str(raw_time_g[t + 1])
                        t_time_marker = re.split(';|,|\n|\t', t_time_marker_raw)[0]
                        time_for_zabbix = int(t_time_value) * int(time_dict[t_time_marker])
                        time_val_dict.update({'time' + str(tt): time_for_zabbix})
                        tt += 1
                return time_val_dict

            except Exception as convert_time_ex:
                logging.error('convert_time exception:{0}; graph_time_range_string: {1}'.format(convert_time_ex, graph_time_range_string))
        else:
            logging.error("'graph_time_range_string' was not found : {0}. Email will be without graphs".format(graph_time_range_string))

# ------------------------convert time for RESUBMIT ---------------------------------
    def convert_time_resubmit(resubmit):
        raw_time_g = re.split('(\d+)', resubmit)
        raw_time_g.remove('')
        global resubmit_time_new
        if raw_time_g[1] == 's':
            S = float(raw_time_g[0])
            resubmit_time_new = datetime.timedelta(seconds=S)
            logging.info('Return  resubmit_time_new. seconds: {0}'.format(resubmit_time_new))
            return resubmit_time_new

        elif raw_time_g[1] == 'm':
            M = float(raw_time_g[0])
            resubmit_time_new = datetime.timedelta(minutes=M)
            logging.info('Return  resubmit_time_new. minutes: {0}'.format(resubmit_time_new))
            return resubmit_time_new
        elif raw_time_g[1] == 'h':
            H = float(raw_time_g[0])
            resubmit_time_new = datetime.timedelta(hours=H)
            logging.info('Return  resubmit_time_new. hours: {0}'.format(resubmit_time_new))
            return resubmit_time_new
        else:
            msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Wrong format for resubmit time !<br>{0}'.format(resubmit)
            msg_log = "Wrong format for resubmit time: {0}".format(resubmit)
            me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Wrong format for resubmit time" + str(zabbix_location)
            email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)

# -----------------------Get data from  Database--------------------------------------
    def mysql_data(id, jiras_count, opened_jira, emailid, itemvalue, trigstatus, operation, studio, procedure, email_subject):
        try:
            mariadb_connection = mariadb.connect(user=mysql_user, password=mysql_password, host=mysql_host, database='automations', connection_timeout=5)
        except mariadb.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR_automail:
                msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Error with connection to DB automations.<br><br>{0}'.format(err)
                msg_log = "Error with connection to DB. {0} - {1}".format(err, zabbix_location)
                me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + str('Error with connection to DB automations - ') + str(zabbix_location)
                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
            elif err.errno == errorcode.ER_BAD_DB_ERROR_automail:
                msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Error with connection to DB automations.<br><br>{0}'.format(err)
                msg_log = "Database does not exist. {0} - {1}".format(err, zabbix_location)
                me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + str('Database automations does not exist - ') + str(zabbix_location)
                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
            else:

                msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Error with connection to DB automations.<br><br>{0}'.format(err)
                msg_log = "Error with connection to DB. {0} - {1}".format(err, zabbix_location)
                me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + str('Error with connection to DB automations - ') + str(zabbix_location)
                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
        else:
            try:
                cursor = mariadb_connection.cursor()
                if operation == "get":
                    cursor.execute('select Email_Id, Time_Stamp, Item_Value, Trigger_Status, jira_count, Open_jira, Email_Subject from `{0}` where Id="{1}";'.format(zabbix_auto_tables[zabbix_location], id))
                    for (Email_Id, Time_Stamp, Item_Value, Trigger_Status, jira_count, Open_jira, Email_Subject) in cursor:
                        result = {'Email_Id': Email_Id, 'Time_Stamp': Time_Stamp, 'Item_Value': Item_Value, 'Trigger_Status': Trigger_Status, 'jira_count': jira_count, 'Open_jira': Open_jira, 'Email_Subject': Email_Subject}
                        logging.info('Operation get from table - {0}, result: {1}'.format(zabbix_auto_tables[zabbix_location], result))
                        return result

                elif operation == "add":
                    cursor.execute('INSERT INTO `{0}` SET Email_Id="{1}", Item_Value="""{2}""", Trigger_Status="{3}", jira_count="{4}", Open_jira="{5}", Id="{6}", Email_Subject="{7}";'.format(zabbix_auto_tables[zabbix_location], emailid, itemvalue, trigstatus, jiras_count, opened_jira, id, str(email_subject).replace('"', '')))
                    mariadb_connection.commit()
                    logging.info('New info was added to db. Table - {0}'.format(zabbix_auto_tables[zabbix_location]))

                elif operation == "update":
                    present = datetime.datetime.now()
                    cursor.execute('UPDATE `{0}` SET Email_Id="{1}", Item_Value="""{2}""", Trigger_Status="{3}", jira_count="{4}", Open_jira="{5}", Time_Stamp="{6}", Email_Subject="{7}" WHERE Id="{8}";'.format(zabbix_auto_tables[zabbix_location], emailid, itemvalue, trigstatus, jiras_count, opened_jira, present, str(email_subject).replace('"', ''), id))
                    mariadb_connection.commit()
                    logging.info('Row with Id-{0} was updated. Table - {1}'.format(id, zabbix_auto_tables[zabbix_location]))

                elif operation == "get_wiki":
                    cursor.execute("SELECT description, graph_time_range, recipients, cc_recipients, resubmit, status, create_jira FROM wiki_syncer WHERE studio='{0}' AND procedure_name='{1}';".format(studio, procedure))
                    for (description, graph_time_range, recipients, cc_recipients, resubmit, status, create_jira) in cursor:
                        result = {'description': description, 'graph_time_range': graph_time_range, 'recipients': recipients,
                                  'cc_recipients': cc_recipients, 'resubmit': resubmit, 'status': status, 'create_jira': create_jira}
                        logging.info('Operation get_wiki, result: {0}'.format(result))
                        return result
                cursor.close()
                mariadb_connection.close()
            except Exception as any_ex:
                msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Error with connection to DB automations, table : {0}<br><br>id - {1}<br>{2}<br>{3}'.format(zabbix_auto_tables[zabbix_location], id, type(any_ex).__name__, any_ex.args)
                msg_log = "Error with connection to DB automations, table: {0}, exception: {1}".format(zabbix_auto_tables[zabbix_location], any_ex)
                me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + str('Error with connection to DB automations - ') + str(zabbix_location)
                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)

# -----------------------Zabbix-api----------------------------------------------
    def login_to_api(zabbix_loc):
        try:
            logging.info("I'm trying to login to Zabbix-API")
            global zabbix
            zabbix = ZabbixAPI(zabbix_hosts[zabbix_loc])
            zabbix.login(zabbix_hosts["user"], zabbix_hosts["zabbix_pass"])
            return
        except Exception as login_api_error:
            print("AUCHTUNG can't login - {0}".format(login_api_error))
            msgg_log = "Can't login - {0}".format(login_api_error)
            logging.critical(msgg_log)


# ------------------------ GET trigger info & send error mail if fail ----------------------------------------
    def get_trigger_info(keyword):
        try:
            logging.info("Getting triggers in 'INFO' state")
            global trigger_list
            trigger_list = zabbix.trigger.get(filter={'value': 1, 'status': 0, 'priority': 1},
                                              selectFunctions=['itemid'], templated=False, state=0, active=True,
                                              withLastEventUnacknowledged=True, expandDescription=1,
                                              output=['triggerid', 'description', 'itemid', 'comments'])
            if len(trigger_list) != 0:
                len_trig_l = len(trigger_list) - 1
                n = 0
                while n <= len_trig_l:
                    elem = trigger_list[n]
                    if elem['comments'] != "" or elem['comments'] is not None:
                        raw_comments = elem['comments']
                        if keyword in str(raw_comments):
                            if not re.search('^Test', str(raw_comments), re.IGNORECASE):
                                global graph_name
                                global trig_id
                                global item_value

                                try:
                                    parameters_dict = json.loads(raw_comments.split(keyword)[1])
                                except Exception as json_ex:
                                    msg_me = '<br>Hi<br><br><font color="red">Email was not sent !</font><br>Wrong JSON format for triggerid - {0}<br><br>Zabbix - {1}<br>Exception: {2}'.format(elem['triggerid'], zabbix_location, json_ex)
                                    msg_log = "Wrong JSON format for triggerid - {0}, Exception - {1}".format(elem['triggerid'], json_ex)
                                    me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + str(
                                        'Wrong JSON format for trigger - ') + str(zabbix_location)
                                    email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                    n = n + 1
                                    continue

                                if 'Graph_name' in parameters_dict:
                                    graph_name = parameters_dict['Graph_name']
                                else:
                                    graph_name = None
                                studio = parameters_dict['Studio']
                                procedure = parameters_dict['Procedure']
                                if (studio is None or studio == "") or (procedure is None or procedure == ""):
                                    logging.warning("Wrong format of Procedure or Studio in desc: {0}".format(studio))
                                    continue
                                else:
                                    if not re.search('^\s|None|^$|^Disable|^disabled', str(graph_name), re.IGNORECASE):
                                        if not re.search('^Test ', str(elem['description']), re.IGNORECASE):

                                            trig_id = elem['triggerid']
                                            host_id = zabbix.host.get(triggerids=trig_id, output=['hostid'])[0]['hostid']
                                            graph_idd = zabbix.graph.get(hostids=host_id, filter={'name': graph_name},
                                                                         output=['name'])
                                            if len(graph_idd) == 1:
                                                if len(elem['functions'][0]) > 1:
                                                    msg_me = 'Hi!<br><br><font color="red">Email was not sent !</font><br>More than one itemID was found cannot get appropriate value, triggerid: {0}.<br>Please check alerts and send corresponding email if needed.<br>'.format(
                                                        trig_id)
                                                    msg_log = "More than one itemID was found can't get appropriate value"
                                                    me_mail_subject = 'ERROR_automail ' + str(date) + str(
                                                        ' - ') + 'More than one itemID was found' + str(zabbix_location)
                                                    email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                    continue
                                                elif len(elem['functions'][0]) == 1:
                                                    tmp_val = elem['functions'][0]['itemid']
                                                    try:
                                                        item_value = zabbix.item.get(itemids=tmp_val, output=['lastvalue'])[0]['lastvalue']
                                                        logging.debug("item_value: {0}".format(item_value))
                                                    except Exception as item_get_ex:
                                                        item_value = "No data"
                                                        logging.error("NO DATA  for triggerid-{0}, Exception: {1}".format(trig_id, item_get_ex))
                                                else:
                                                    msg_me = 'Hi!<br><br><font color="red">Email was not sent !</font><br>Wrong itemID was found for - triggerid: {0}.<br>Please check alerts and send corresponding email if needed.<br>'.format(
                                                        trig_id)
                                                    msg_log = "Wrong itemID was found for triggerid: {0}".format(trig_id)
                                                    me_mail_subject = 'ERROR_automail ' + str(date) + str(
                                                        ' - ') + 'Wrong itemID was found' + str(zabbix_location)
                                                    email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                    continue
                                                id = graph_idd[0]['graphid']
                                                url_t = 'graph'
                                                elem.update({'item_value': item_value})
                                                elem.update({'Studio': studio})
                                                elem.update({'Procedure': procedure})
                                                elem.update({'id': id})
                                                elem.update({'url_t': url_t})
                                                trigger_list[n] = elem
                                                logging.debug("elem : {0}".format(elem))
                                            elif len(graph_idd) < 1:
                                                logging.info("len(graph_idd)={0}".format(len(graph_idd)))
                                            else:
                                                msg_me = 'Hi!<br><br><font color="red">Email was not sent !</font><br>More than one match was found in Graph Names. I do not know which  graph chose!<br><i>{0}</i><br>'.format(
                                                    graph_idd)
                                                msg_log = "More than one match was found in Graph Names: {0}".format(
                                                    graph_idd)
                                                me_mail_subject = 'ERROR_automail ' + str(date) + str(
                                                    ' - ') + 'More than one match was found in Graph Names' + str(
                                                    zabbix_location)
                                                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                continue
                                        else:
                                            logging.info("Word TEST was found in description {0}. Ignoring.".format(
                                                elem['description']))
                                            # continue
                                    elif re.search('^Disable|^disabled', str(graph_name), re.IGNORECASE):
                                        if not re.search('^Test ', str(elem['description']), re.IGNORECASE):
                                            logging.info("graph_name was set to DISABLED, so NO graph/link will be attached")
                                            trig_id = elem['triggerid']
                                            id = elem['functions'][0]['itemid']
                                            tmp_val = elem['functions'][0]['itemid']

                                            try:
                                                item_value = zabbix.item.get(itemids=tmp_val, output=['lastvalue'])[0]['lastvalue']
                                                logging.debug("item_value: {0}".format(item_value))
                                            except Exception as item_get_ex:
                                                logging.warning("NO DATA  for triggerid-{0}, exception: {1}".format(trig_id, item_get_ex))
                                                item_value = ""
                                            url_t = 'no_graph'
                                            elem.update({'item_value': item_value})
                                            elem.update({'Studio': studio})
                                            elem.update({'Procedure': procedure})
                                            elem.update({'id': id})
                                            elem.update({'url_t': url_t})
                                            trigger_list[n] = elem
                                            logging.debug("elem : {0}".format(elem))
                                        else:
                                            logging.info("Word TEST was found in description {0}. Ignoring.".format(
                                                elem['description']))
                                    else:
                                        if not re.search('^Test ', str(elem['description']), re.IGNORECASE):
                                            trig_id = elem['triggerid']
                                            id = elem['functions'][0]['itemid']
                                            tmp_val = elem['functions'][0]['itemid']
                                            try:
                                                item_value = zabbix.item.get(itemids=tmp_val, output=['lastvalue'])[0]['lastvalue']
                                                logging.debug("item_value: {0}".format(item_value))
                                            except Exception as item_get_ex:
                                                item_value = "No data"
                                                logging.warning("NO DATA  for triggerid-{0}, exception: {1}".format(trig_id, item_get_ex))

                                            elem.update({'item_value': item_value})
                                            elem.update({'Studio': studio})
                                            elem.update({'Procedure': procedure})
                                            elem.update({'id': id})
                                            url_t = 'latest'
                                            elem.update({'url_t': url_t})
                                            trigger_list[n] = elem
                                            logging.debug("elem : {0}".format(elem))
                                            logging.info("Latest-data graph will be attached")
                                        else:
                                            logging.info("Word TEST was found in description {0}. Ignoring.".format(elem['description']))
                            else:
                                logging.info("Ignoring alert. TEST was found in alerts comment.")
                        else:
                            logging.info("Ignoring alert. Keyword {0} was not found in description.\n"
                                         "Trigger: {1}".format(keyword, elem['description']))
                    else:
                        logging.info("Ignoring alert. Comments field is empty: {0}.".format(elem['comments']))
                        continue
                    n = n + 1
                return trigger_list
            else:
                logging.info("No INFO triggers were found")
        except Exception as trigger_get_ex:
            msg_me = 'Hi!<br><br><font color="red">Email was not sent !</font><br>Cannot get full info regarding triggers via API. Exception: {0}<br><br>Please check.<br>'.format(
                trigger_get_ex)
            msg_log = "Can't get full info. Exception: {0}".format(trigger_get_ex)
            me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + 'Cannot get triggers info via API-' + str(zabbix_location)
            email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)

# ---------------------------------- Convert time to Human format --------------------------------------------------
    def time_human_format(time):
        try:
            logging.info("Executing time_human_format function")
            if time != 0 and time != "":
                if time / 3600 > 24:
                    period = "{0} days".format(time / 3600 / 24)
                    logging.debug("time_human_format: {0}".format(period))
                    return period
                elif time / 3600 == 24:
                    period = "day"
                    logging.debug("time_human_format: {0}".format(period))
                    return period
                else:
                    period = "{0} hours".format(time / 3600)
                    logging.debug("time_human_format: {0}".format(period))
                    return period
            else:
                logging.warning("time_human_format is Null: {0}".format(time))
        except Exception as time_human_format_ex:
            logging.warning("time_human_format exception: {0}".format(time_human_format_ex))

    def modification_date(filename):
        t = os.path.getmtime(filename)
        logging.debug("modification_date: {0}".format(datetime.datetime.fromtimestamp(t)))
        return datetime.datetime.fromtimestamp(t)

# -----------------------email-function (with INCIDENT) -------------------------------------------------------------
    def email_inc(text, keys_url, downloaded_images_name, email_id, mail_subject, recipients, cc_recipients):
        global res_email_sent
        try:
            logging.info("I'm trying to send email with Incident...")
            msgRoot = MITeamMultipart('related')
            msgRoot['Subject'] = mail_subject
            msgRoot['From'] = "nocteam@test.com"
            msgRoot['To'] = ', '.join(recipients)
            msgRoot['Cc'] = ', '.join(cc_recipients)
            msgRoot.add_header("Message-ID", email_id)
            msgRoot.add_header("References", email_id)
            msgRoot.preamble = 'This is a multi-part message in MITeam format.'
            msgAlternative = MITeamMultipart('alternative')
            msgRoot.attach(msgAlternative)
            msgText = MITeamText("")
            msgAlternative.attach(msgText)
            msgText = MITeamText(text, 'html')
            msgAlternative.attach(msgText)
            if keys_url and downloaded_images_name:
                for f in keys_url:
                    fp = open(downloaded_images_name[f], 'rb')
                    msgImage = MITeamImage(fp.read())
                    fp.close()
                    # Define the image's ID as referenced above
                    msgImage.add_header('Content-ID', '<{0}>'.format(f))
                    msgRoot.attach(msgImage)
            send = smtplib.SMTP(mail_server_address)
            send.send_message(msgRoot)
            send.close()
            logging.info("Email was sent - OK: {0}".format(mail_subject))
            res_email_sent = 0
            return res_email_sent
        except Exception as email_exeption:
            logging.critical("Email was NOT sent! Troubles with email-sender: {0}".format(email_exeption))
            res_email_sent = 1
            return res_email_sent
# -------------------------------------------------------------------------------------------------------------
    login_to_api(zabbix_location)
    get_trigger_info(keyword)
    ## Check if link is available
    try:
        r = requests.get(web_url, timeout=10)
        r.status_code
    except Exception as statuscode:
        msg_me = 'Hi!<br><br><font color="red">Email was not sent !</font><br>It seems Zabbix: {0} is unreachable.<br>Please check.<br>Error: {1}'.format(web_url, statuscode)
        msg_log = "It seems Zabbix is unreachable: {0}, {1}".format(web_url, statuscode)
        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "It seems Zabbix {0} is unreachable".format(zabbix_location)
        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)

# -------------------------------------- Create JIRA ----------------------------------------------------------------
    def create_jira(jira_user, jira_password, img, mail_subject, msg_jira, project_jira):
        issue_dict = {
        'project': project_jira,
        'summary': '{0}'.format(mail_subject),
        'description': msg_jira,
        'issuetype': {'name': 'Task'},
    }
        try:
            jira_options = {'server': jira_server}
            jira = JIRA(options=jira_options,
                        # Note the tuple
                        basic_auth=(jira_user, jira_password), timeout=10)
            global opened_jira
            global create_jira_res
            global jira_link
            global j_k
            if opened_jira and ((opened_jira != "") and (opened_jira is not None) and (opened_jira != "*****")):
                try:
                    prev_issue = jira.issue(opened_jira)
                    prev_issue_status = prev_issue.fields.status
                    if re.search('Done|Closed', str(prev_issue_status), re.IGNORECASE):
                        logging.info("Creating new JIRA")
                        new_jira = jira.create_issue(fields=issue_dict)
                        if img:
                            jira.add_attachment(issue=new_jira, attachment=img)
                            with open(img, 'rb') as f:
                                 jira.add_attachment(issue=new_jira, attachment=f)
                        j_k = new_jira.key
                        jira_link = "{0}/browse/{1}".format(jira_server, j_k)
                        logging.info("JIRA: {0} was created.".format(j_k))
                        create_jira_res = 0
                    else:
                        logging.info("JIRA: {0} still not Done/Closed.".format(prev_issue))
                        create_jira_res = 1
                except Exception as jira_cxe:
                    msg_me = 'Hi!<br><br><font color="red">Jira was not created !</font><br>Please check<br>{0}'.format(jira_cxe)
                    msg_log = "Failed when creating JIRA: {0}".format(jira_cxe)
                    me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "JIRA failed - {0}".format(
                        zabbix_location)
                    email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                    create_jira_res = 1

            else:
                logging.info("Creating new JIRA")
                new_jira = jira.create_issue(fields=issue_dict)
                if img:
                    jira.add_attachment(issue=new_jira, attachment=img)
                    with open(img, 'rb') as f:
                        jira.add_attachment(issue=new_jira, attachment=f)
                j_k = new_jira.key
                jira_link = "{0}/browse/{1}".format(jira_server, j_k)
                logging.info("JIRA: {0} was created.".format(j_k))
                create_jira_res = 0
        except Exception as con_ex:
            logging.error("Failed to connect to JIRA: {0}".format(con_ex))
            template = 'Hi!<br><br><font color="red">Jira was not created !</font><br>Jira was not created for:{0}<br>An exception of type: {1} occurred. Arguments:<br>{2!r}<br>Please check<br>'
            msg_me = template.format(mail_subject, type(con_ex).__name__, con_ex.args)
            msg_log = "Failed to connect to JIRA: {0}".format(con_ex)
            me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Connection to JIRA failed - {0}".format(zabbix_location)
            email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
            create_jira_res = 1

# -------------------------- Login to WEB-UI for getting cookies ----------------------------------------------------
    def login_to_site(web_url):
        logging.info("Login to Zabbix UI")
        browser = webdriver.PhantomJS(driver_path, service_log_path='/tmp/ghostdriver_log.log')
        browser.get(web_url)
        user = browser.find_element_by_id('name')
        passwd = browser.find_element_by_id('password')
        #button = browser.find_element_by_id('enter')
        try:
            user.clear()
            passwd.clear()
            user.send_keys(username)
            passwd.send_keys(password)
            #button.click()
            passwd.send_keys(Keys.RETURN)
            assert "is incorrect" not in browser.page_source
            temp_cookies = pickle.dumps(browser.get_cookies())
            global cookies
            cookies = pickle.loads(temp_cookies)
            logging.info("login_to_site get cookies")
            logging.debug("login_to_site - cookies: {0}".format(cookies))
            return cookies
        except AssertionError as login_error:
            msg_me = 'Hi!<br><br><font color="red">Email was not sent !</font><br><br>Please check triggers in Zabbix and send corresponding email if needed.<br><br><b>Monitoring Experts </b> - please check the automation sscript.<br>Login Error: {0}'.format(login_error)
            msg_log = "Can't login to Zabbix UI: {0}. {1}".format(web_url, login_error)
            me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + 'Login to zabbix - {0}'.format(zabbix_location)
            email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)

    login_to_site(web_url)

# ---------------------------- Login to WEB-UI with cookies and get image -------------------------------------------
    def image_dow(id, cookies, urls_images):
        for cookie in cookies:
            if cookie['name'] == 'zbx_sessionid':
                k = {cookie['name']: cookie['value']}
                urls_images_keys = (sorted(urls_images.keys()))
                global downloaded_images_name
                downloaded_images_name = {}
                logging.info("I'm downloading corresponding images now...")
                for key in urls_images_keys:
                    graph = urls_images[key][1]
                    response = requests.get(graph, cookies=k)
                    if response.status_code != 200:
                        msg_me = 'Hi!<br><br><b><font color="red">Email was not sent !</font></b><br>It seems wrong link to  the graph or Zabbix is unreachable:  {0}.<br>Please check corresponding alerts  and send corresponding email if needed.'.format(
                            graph)
                        msg_log = "It seems wrong link to  the graph or Zabbix is unreachable: {0}. {1} ".format(graph, response.status_code)
                        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + 'Login to Zabbix {0}'.format(zabbix_location)
                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                        time.sleep(2)
                        continue
                    else:
                        rand = randint(0, 9999)
                        graph_name = str('/tmp/') + str(todayd) + str('_') + str(id) + str(rand) + str(zabbix_location) + '.png'
                        with open(graph_name, 'wb') as out_file:
                            out_file.write(response.content)
                        downloaded_images_name.update({key: graph_name})
                        logging.info("Image was downloaded: {0}".format(graph_name))
                return downloaded_images_name
            else:
                logging.debug("Wrong cookie: {0}".format(cookie['name']))

# -------------------------------------- Load data for catched triggers and processing (step by step) -------------------
    def load_one_by_one(triggers_data, cookies, email_hours_same_thread):
        for j in triggers_data:
            if not j or j == "":
                msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Step load_one_by_one, cannot find corresponding info<br><br>'
                msg_log = "Step load_one_by_one, cannot find corresponding info"
                me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Step load_one_by_one, cannot find corresponding info " + zabbix_location
                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                continue
            if (len(j) < 4) or ('Studio' not in j['comments']) or ('Procedure' not in j['comments']):
                msg_log = "Wrong quantity of arguments or Studio or Procedure not found in desc: {0}.".format(j['comments'])
                logging.warning(msg_log)
                continue
            else:
                logging.info(" ")
                logging.info(".........load_one_by_one: next one............")

                logging.info(j)
                global opened_jira
                global url_zab
                global create_jira_res
                global j_k
                global cc_recipients
                global jira_link
                global item_value
                create_jira_res = 1
                j_k = ""
                opened_jira = ""
                jiras_count = 0
                jira_link = ""
                if 'item_value' not in j or ('Studio' not in j or 'Procedure' not in j):
                    msg_me = """<br>Hi!<br><br><b><font color="red">Email can not be sent without data!</font></b><br>
                    <br>Step load_one_by_one, cannot find corresponding info.<br>Possible issues:
                    <br>1 - 'item_value' was not found for trigger;<br>2 - 'Studio' was not found for trigger;
                    <br>3 - 'Procedure' was not found for trigger;<br><br>So, ALL what I have:<br>{0}""".format(j)
                    msg_log = "Step load_one_by_one, cannot find corresponding info-{0}, {1}".format(j, zabbix_location)
                    me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Step load_one_by_one, cannot find corresponding info for trigger " + zabbix_location
                    email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                    time.sleep(3)
                    continue
                else:
                    item_value = j['item_value']
                    studio = j['Studio']
                    procedure = j['Procedure']
                    trig_id = j['triggerid']
                trigger_name = j['description']
                id = j['id']
                url_t = j['url_t']
                if url_t == 'graph':
                    url_zab = str(web_url) + 'charts.php?graphid=' + str(id)
                elif url_t == 'no_graph':
                    url_zab = 'no_graph'
                else:
                    url_zab = str(web_url) + 'history.php?action=showgraph&itemids[]=' + str(id)

# ------------------------------- Get (WIKI) info from automations db -------------------------------------------------
                logging.info("Load data from WIKI DB")
                wiki_data = mysql_data(trig_id, '', '', '', '', '', 'get_wiki', studio, procedure, '')
                if (wiki_data is None) or ('@' not in wiki_data['recipients']):
                    id_link = zabbix_hosts[zabbix_location] + "triggers.php?form=update&triggerid=" + str(trig_id)
                    msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Cannot get full data from DB: "automations", table "wiki_syncer"<br>{0}<br><a href="{1}">Trigger Id {2}</a>, studio - {3}, procedure - {4}'.format(wiki_data, id_link, trig_id, studio, procedure)
                    msg_log = "Cannot get full data from DB: 'automations', table 'wiki_syncer' - Id-{0}, studio - {1}, procedure - {2}".format(trig_id, studio, procedure)
                    me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Can't get Wiki_Data from DB automations - {0}".format(zabbix_location)
                    email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                    time.sleep(3)
                    continue
                else:
                    recipients = parce_recipients(wiki_data['recipients'])
                    logging.debug("recipients: {0}".format(recipients))
                    if '@' not in wiki_data['cc_recipients']:
                        cc_recipients = []
                    else:
                        cc_recipients = parce_recipients(wiki_data['cc_recipients'])
                    logging.debug("cc_recipients: {0}".format(cc_recipients))
                    resubmit = wiki_data['resubmit']

                    status_t = wiki_data['status']
                    trigger_jira = wiki_data['create_jira']
                    graph_time_range = wiki_data['graph_time_range']
                    description_wiki = wiki_data['description']
                    logging.debug("resubmit: {0}".format(resubmit))
                    logging.debug("status_t: {0}".format(status_t))
                    logging.debug("graph_time_range: {0}".format(graph_time_range))
                    logging.debug("description_wiki: {0}".format(description_wiki))
                    if status_t == "" or status_t is None:
                        msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>Cannot get FULL data from wiki_data <br>status trigger: {0}<br>{1}'.format(status_t, wiki_data)
                        msg_log = "Cannot get FULL data from wiki_data. status_t: {0}".format(status_t)
                        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Can't get FULL data from wiki_data"
                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                        time.sleep(2)
                        continue
                    else:
                        convert_time(graph_time_range)
                        keys = (sorted(time_val_dict.keys()))
                        urls_images = {}
                        for k in keys:
                            if url_t == 'graph':
                                url = str(web_url) + 'chart2.php?graphid=' + str(id) + '&period=' + str(time_val_dict[k])
                                urls_images.update({'url_' + str(k): [time_val_dict[k], url]})

                            else:
                                url = str(web_url) + 'chart.php?period=' + str(time_val_dict[k]) + '&itemids%5B0%5D=' + str(id)
                                urls_images.update({'url_' + str(k): [time_val_dict[k], url]})
                        logging.debug("Images: {0}".format(urls_images))
                        mysqlData = mysql_data(trig_id, '', '', '', '', '', 'get', '', '', '')
                        if mysqlData == None:
                            logging.info("No data regarding this trigger was found in DB, so it's new one")
                            if status_t == 'Active' or status_t == 'active':
                                mail_subject = "[AUTO] " + str(date) + str(' - ') + str(studio) + " " + str(j['description']) + " tr-{0}".format(trig_id)
                                logging.info("Trigger is Active: {0}".format(trig_id))
                                email_id = make_msgid()
                                logging.info("Email-Id - {0}".format(email_id))
                                if url_zab == 'no_graph':
                                    logging.info("url_zab is None so NO images and links will be attached")
                                    inc_msg = ['<br>Hi!<br><br>We have received an alert about: <br>{0} - {1}<br><br>'.format(trigger_name, item_value)]
                                    inc_msg.append(description_wiki)

                                    if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                        jira_msg = 'Hi!\n\nWe have received an alert about:\n{0} - {1}\n\nPlease check.'.format(trigger_name, item_value)

                                        create_jira(jira_user, jira_password, '', mail_subject, jira_msg, trigger_jira)
                                        if create_jira_res == 0:
                                            opened_jira = j_k
                                            jiras_count = 1
                                            inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                    jira_link, time_seconds))
                                        else:
                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                    time_seconds))
                                    else:
                                        inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                time_seconds))
                                    final_inc_msg = ''.join(inc_msg)
                                    try:
                                        email_inc(final_inc_msg, '', '', email_id, mail_subject, recipients, cc_recipients)
                                        if res_email_sent == 0:
                                            mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'add', '', '', mail_subject)
                                            logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                            time.sleep(5)
                                            continue
                                        else:
                                            logging.error("First email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                            continue
                                    except Exception as ex:
                                        msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check the alerts and send corresponding email if needed.<br>Maybe sometning went wrong with mail-server.<br>Team - Please check the log file: {0} <br>Error:  {1}'.format(
                                            log_file, ex)
                                        msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Sometning went wrong with email sender"
                                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                        time.sleep(2)
                                        continue
                                else:
                                    image_dow(id, cookies, urls_images)
                                    # email header
                                    inc_msg = ['<br>Hi!<br><br>We have received an alert about: <br>{0} - {1}<br><br><a href={2}>Link</a> to Zabbix.<br>'.format(trigger_name, item_value, url_zab)]

                                    inc_msg.append(description_wiki)
                                    keys_url = (sorted(urls_images.keys()))
                                    # graphs from zabbix
                                    for ku in keys_url:
                                        t_time = urls_images[ku][0]
                                        inc_msg.append('<br>Corresponding graph for the last {0} (UTC):'.format(time_human_format(t_time)))
                                        inc_msg.append('<br><br><img src="cid:{0}"><br>'.format(ku))
                                    # footer of the email and jira if needed
                                    if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                        jira_msg = 'Hi!\n\nWe have received an alert about:\n{0} - {1}\n\nLink to Zabbix {2}.\n\nPlease check.'.format(trigger_name, item_value, url_zab)

                                        create_jira(jira_user, jira_password, downloaded_images_name['url_time1'], mail_subject, jira_msg, trigger_jira)
                                        if create_jira_res == 0:
                                            opened_jira = j_k
                                            jiras_count = 1
                                            inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                    jira_link, time_seconds))
                                            logging.info("Adding JIRA link to email. Id-{0}".format(trig_id))
                                        else:
                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                    time_seconds))

                                    else:

                                        inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(time_seconds))

                                    final_inc_msg = ''.join(inc_msg)
                                    try:
                                        logging.info("Email-Id_check - {0}".format(email_id))
                                        email_inc(final_inc_msg, keys_url, downloaded_images_name, email_id, mail_subject, recipients, cc_recipients)
                                        for u in keys_url:
                                            if os.path.isfile(downloaded_images_name[u]):
                                                os.remove(downloaded_images_name[u])
                                                logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                        if res_email_sent == 0:
                                            mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'add', '', '', mail_subject)

                                            logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                            time.sleep(5)
                                            continue
                                        else:
                                            logging.error("First email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                            continue
                                    except Exception as ex:
                                        for u in keys_url:
                                            if os.path.isfile(downloaded_images_name[u]):
                                                os.remove(downloaded_images_name[u])
                                                logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                        msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check the alerts and send corresponding email if needed.<br>Maybe sometning went wrong with mail-server.<br>Team - Please check the log file: {0} <br>Error:  {1}'.format(
                                            log_file, ex)
                                        msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Sometning went wrong with email sender"
                                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                        time.sleep(2)
                                        continue
                            else:
                                logging.info("Trigger is disabled, Id-{0}".format(trig_id))
                                continue
                        else:
                            logging.info("Some data regarding this trigger was found in DB")
                            try:
                                if status_t == 'Active' or status_t == 'active':
                                    email_id = mysqlData['Email_Id']
                                    mail_subject = mysqlData['Email_Subject']
                                    logging.info("Email-Id - {0}".format(email_id))
                                    time_stamp = mysqlData['Time_Stamp']
                                    jiras_count = mysqlData['jira_count']
                                    opened_jira = mysqlData['Open_jira']
                                    present = datetime.datetime.now()
                                    const_time_new = datetime.timedelta(hours=email_hours_same_thread, minutes=1)
                                    if time_stamp < present:
                                        unix_time_last_change = time.mktime(time_stamp.timetuple())
                                        last_tr_change_since = zabbix.trigger.get(lastChangeSince=unix_time_last_change, filter={'triggerid': trig_id}, templated=False, state=0, output=['triggerid'])
                                        if last_tr_change_since:
                                            #after 24 hours 2 minutes this will be new thread
                                            time_difference = abs(present - time_stamp)
                                            if time_difference < const_time_new:
                                                logging.info("Data is not expired. Sending email to the same thread , Id-{0}".format(trig_id))
                                                logging.debug("mail_option - Reply-To")
                                                # if opened_jira and (opened_jira != "") and (opened_jira is not None):
                                                #     prev_issue = jira.issue(opened_jira.split('browse/')[1])
                                                #     prev_issue_status = prev_issue.fields.status
                                                #     if not re.search('Done|Closed', str(prev_issue_status), re.IGNORECASE):
                                                #         logging.info("I've found JIRA - {0} and it seems it's not closed. So I'll not spamming.".format(prev_issue))
                                                #         continue
                                                if url_zab == 'no_graph':
                                                    logging.info("url_zab is None so NO images and links will be attached")
                                                    # email header
                                                    inc_msg = ['<br>UPD<br><br>Hi!<br><br>We received an alert about: <br>{0} - {1}<br><br>'.format(trigger_name, item_value)]
                                                    inc_msg.append(description_wiki)
                                                    if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                                        jira_msg = 'Hi!\n\nWe have an alert about:\n{0} - {1}\n\nPlease check.'.format(trigger_name, item_value)

                                                        create_jira(jira_user, jira_password, '', mail_subject, jira_msg, trigger_jira)
                                                        if create_jira_res == 0:
                                                            jiras_count = int(mysqlData['jira_count']) + 1
                                                            opened_jira = j_k
                                                            inc_msg.append(
                                                                '<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                                    jira_link, time_seconds))
                                                        else:
                                                            inc_msg.append(
                                                                '<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                    time_seconds))
                                                    else:
                                                        inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(time_seconds))
                                                    final_inc_msg = ''.join(inc_msg)
                                                    try:
                                                        email_inc(final_inc_msg, None, None, email_id, mail_subject, recipients, cc_recipients)
                                                        if res_email_sent == 0:

                                                            mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'update', '', '', mail_subject)
                                                            logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                                            time.sleep(5)
                                                            continue
                                                        else:
                                                            logging.error("First email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                                            continue
                                                    except Exception as ex:
                                                        msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check the alerts and send corresponding email if needed.<br>Maybe sometning went wrong with mail-server.<br>Team - Please check the log file: {0} <br>Error:  {1}'.format(
                                                            log_file, ex)
                                                        msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                                        me_mail_subject = 'ERROR_automail ' + str(date) + str(
                                                            ' - ') + "Sometning went wrong with email sender"
                                                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now,
                                                                    msg_log)
                                                        time.sleep(2)
                                                        continue
                                                else:
                                                    image_dow(id, cookies, urls_images)
                                                    # email header
                                                    inc_msg = ['<br>UPD<br><br>Hi!<br><br>We received an alert about: <br>{0} - {1}<br><br><a href={2}>Link</a> to Zabbix.<br>'.format(trigger_name, item_value, url_zab)]
                                                    # description_wiki
                                                    inc_msg.append(description_wiki)
                                                    keys_url = (sorted(urls_images.keys()))
                                                    logging.debug("keys_url - {0}".format(keys_url))
                                                    # graphs from zabbix
                                                    for ku in keys_url:
                                                        t_time = urls_images[ku][0]
                                                        inc_msg.append('<br>Corresponding graph for the last {0} (UTC):'.format(time_human_format(t_time)))
                                                        inc_msg.append('<br><br><img src="cid:{0}"><br>'.format(ku))
                                                    if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                                        jira_msg = 'Hi!\n\nWe have an alert about:\n{0} - {1}\n\nLink to Zabbix {2}.\n\nPlease check.'.format(trigger_name, item_value, url_zab)

                                                        create_jira(jira_user, jira_password, downloaded_images_name['url_time1'], mail_subject, jira_msg, trigger_jira)
                                                        if create_jira_res == 0:
                                                            jiras_count = int(mysqlData['jira_count']) + 1
                                                            opened_jira = j_k
                                                            inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                                    jira_link, time_seconds))
                                                        else:
                                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                    time_seconds))

                                                        logging.info("Adding JIRA link to email. Id-{0}".format(trig_id))
                                                    else:
                                                        jira_link = ''

                                                        # footer of the email
                                                        inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(time_seconds))
                                                    final_inc_msg = ''.join(inc_msg)
                                                    try:
                                                        logging.debug("Id-{0}; recipients: {1}; cc_recipients: {2}".format(trig_id, recipients, cc_recipients))
                                                        logging.info("Email-Id_check - {0}".format(email_id))
                                                        email_inc(final_inc_msg, keys_url, downloaded_images_name, email_id, mail_subject, recipients, cc_recipients)
                                                        for u in keys_url:
                                                            if os.path.isfile(downloaded_images_name[u]):
                                                                os.remove(downloaded_images_name[u])
                                                                logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                                        if res_email_sent == 0:

                                                            mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'update', '', '', mail_subject)
                                                            logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                                            time.sleep(5)
                                                            continue
                                                        else:
                                                            logging.error("Email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                                            continue
                                                    except Exception as ex:
                                                        for u in keys_url:
                                                            if os.path.isfile(downloaded_images_name[u]):
                                                                os.remove(downloaded_images_name[u])
                                                                logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                                        msg_me = 'Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check alerts and send corresponding email if needed.<br>Sometning went wrong with mail-server or script.<br><b>Team</b>- Please check the log file: {0} <br>Error:  {1}'.format(
                                                            log_file, ex)
                                                        msg_log = "Sometning went wrong with email sender: {0}".format(ex)

                                                        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Sometning went wrong with email sender"
                                                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                        time.sleep(2)
                                                        continue
                                            else:
                                                logging.info("Data expired. Difference more than {0}, so I'm sending email to the fresh thread , Id-{1}".format(const_time_new, trig_id))
                                                email_id = make_msgid()
                                                logging.info("Email-Id - {0}".format(email_id))

                                                mail_subject = "[AUTO] " + str(date) + str(' - ') + str(studio) + " " + str(j['description']) + " tr-{0}".format(trig_id)
                                                if url_zab == 'no_graph':
                                                    logging.info("url_zab is None so NO images and links will be attached")
                                                    # email header
                                                    inc_msg = ['<br>Hi!<br><br>We have received an alert about: <br>{0} - {1}<br><br>'.format(trigger_name, item_value)]
                                                    inc_msg.append(description_wiki)
                                                    if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                                        jira_msg = 'Hi!\n\nWe have received an alert about:\n{0} - {1}\n\nPlease check.'.format(trigger_name, item_value)

                                                        create_jira(jira_user, jira_password, '', mail_subject, jira_msg, trigger_jira)
                                                        if create_jira_res == 0:
                                                            opened_jira = j_k
                                                            jiras_count = int(mysqlData['jira_count']) + 1
                                                            inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                                    jira_link, time_seconds))
                                                        else:
                                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                    time_seconds))
                                                    else:
                                                        inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                time_seconds))
                                                    final_inc_msg = ''.join(inc_msg)
                                                    try:
                                                        email_inc(final_inc_msg, None, None, email_id, mail_subject, recipients, cc_recipients)
                                                        if res_email_sent == 0:
                                                            mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'update', '', '', mail_subject)
                                                            logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                                            time.sleep(5)
                                                            continue
                                                        else:
                                                            logging.error("First email was NOT send ! Data in DB was not updated. Id - {0}".format(
                                                                trig_id))
                                                            continue
                                                    except Exception as ex:
                                                        msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check the alerts and send corresponding email if needed.<br>Maybe sometning went wrong with mail-server.<br>Team - Please check the log file: {0} <br>Error:  {1}'.format(
                                                            log_file, ex)
                                                        msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                                        me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Sometning went wrong with email sender"
                                                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                        time.sleep(2)
                                                        continue
                                                else:
                                                    image_dow(id, cookies, urls_images)
                                                    # email header
                                                    inc_msg = ['<br>Hi!<br><br>We have received an alert about: <br>{0} - {1}<br><br><a href={2}>Link</a> to Zabbix.<br>'.format(trigger_name, item_value, url_zab)]
                                                    # description_wiki   maybe this need to input in email body
                                                    inc_msg.append(description_wiki)
                                                    keys_url = (sorted(urls_images.keys()))
                                                    # graphs from zabbix
                                                    for ku in keys_url:
                                                        t_time = urls_images[ku][0]
                                                        inc_msg.append('<br>Corresponding graph for the last {0} (UTC):'.format(
                                                            time_human_format(t_time)))
                                                        inc_msg.append('<br><br><img src="cid:{0}"><br>'.format(ku))
                                                    # footer of the email
                                                    if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                                        jira_msg = 'Hi!\n\nWe have received an alert about:\n{0} - {1}\n\nLink to Zabbix {2}.\n\nPlease check.'.format(trigger_name, item_value, url_zab)

                                                        create_jira(jira_user, jira_password, downloaded_images_name['url_time1'], mail_subject, jira_msg, trigger_jira)
                                                        if create_jira_res == 0:
                                                            opened_jira = j_k
                                                            jiras_count = int(mysqlData['jira_count']) + 1
                                                            inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(jira_link, time_seconds))
                                                        else:
                                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                    time_seconds))
                                                    else:

                                                        inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(time_seconds))

                                                    final_inc_msg = ''.join(inc_msg)
                                                    try:
                                                        logging.debug("Id-{0}; recipients: {1}; cc_recipients: {2}".format(trig_id, recipients, cc_recipients))
                                                        logging.info("Email-Id_check - {0}".format(email_id))
                                                        email_inc(final_inc_msg, keys_url, downloaded_images_name, email_id, mail_subject, recipients, cc_recipients)
                                                        for u in keys_url:
                                                            if os.path.isfile(downloaded_images_name[u]):
                                                                os.remove(downloaded_images_name[u])
                                                                logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                                        if res_email_sent == 0:
                                                            mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'update', '', '', mail_subject)
                                                            logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                                            time.sleep(5)
                                                            continue
                                                        else:
                                                            logging.error("FIRST Email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                                            continue
                                                    except Exception as ex:
                                                        for u in keys_url:
                                                            if os.path.isfile(downloaded_images_name[u]):
                                                                os.remove(downloaded_images_name[u])
                                                                logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                                        msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check corresponding alerts and send corresponding email if needed.<br>Sometning went wrong with email sender.<br>Team - Please check the log file: {0} <br>Error:  {1}'.format(
                                                            log_file, ex)
                                                        msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                                        me_mail_subject = 'ERROR_automail ' + str(date) + str(
                                                            ' - ') + "Sometning went wrong with email sender" + str(zabbix_location)
                                                        email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                        time.sleep(2)
                                                        continue
                                        else:
                                            logging.info("Trigger state was not changed since - {0}. I'll try to resubmit.".format(time_stamp))
                                            logging.debug("I'm going to check and send UPD to the previous thread.")
                                            ## section for resubmit even trigger-state was not changed
                                            if resubmit and (resubmit != "" and (resubmit != 'False' and resubmit != 'false')):
                                                logging.debug("Resubmit time: {0}".format(resubmit))
                                                convert_time_resubmit(resubmit)
                                                time_difference = abs(present - time_stamp)
                                                logging.debug("time_difference: {0}".format(time_difference))
                                                if time_difference > resubmit_time_new:
                                                    logging.info("Time difference more than resubmit_time so I'm going to UPD the same thread")
                                                    email_id = mysqlData['Email_Id']
                                                    mail_subject = mysqlData['Email_Subject']
                                                    logging.info("Email-Id - {0}".format(email_id))

                                                    logging.debug("opened_jira - {0}".format(opened_jira))
                                                    logging.debug("mail_option - Reply-To")
                                                    if url_zab == 'no_graph':
                                                        logging.info("url_zab is None so NO images and links will be attached")
                                                        # email header
                                                        inc_msg = ['<br>UPD<br><br>Hi!<br><br>We still have an alert about: <br>{0} - {1}<br><br>'.format(trigger_name, item_value)]
                                                        inc_msg.append(description_wiki)
                                                        if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                                            jira_msg = 'Hi!\n\nWe still have an alert about:\n{0} - {1}\n\nPlease check.'.format(trigger_name, item_value)

                                                            create_jira(jira_user, jira_password, '', mail_subject, jira_msg, trigger_jira)
                                                            if create_jira_res == 0:
                                                                opened_jira = j_k
                                                                jiras_count = int(mysqlData['jira_count']) + 1
                                                                inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                                        jira_link, time_seconds))
                                                            else:
                                                                inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                        time_seconds))
                                                        else:
                                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                    time_seconds))
                                                        final_inc_msg = ''.join(inc_msg)
                                                        try:
                                                            email_inc(final_inc_msg, None, None, email_id, mail_subject,
                                                                      recipients, cc_recipients)
                                                            if res_email_sent == 0:

                                                                mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'update', '', '', mail_subject)
                                                                logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                                                time.sleep(5)
                                                                continue
                                                            else:
                                                                logging.error("First email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                                                continue
                                                        except Exception as ex:
                                                            msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check the alerts and send corresponding email if needed.<br>Maybe sometning went wrong with mail-server.<br>Team - Please check the log file: {0} <br>Error:  {1}'.format(
                                                                log_file, ex)
                                                            msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                                            me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "Sometning went wrong with email sender"
                                                            email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                            time.sleep(2)
                                                            continue
                                                    else:
                                                        image_dow(id, cookies, urls_images)
                                                        # email header
                                                        inc_msg = ['<br>UPD<br><br>Hi!<br><br>We still have an alert about: <br>{0} - {1}<br><br><a href={2}>Link</a> to Zabbix.<br>'.format(trigger_name, item_value, url_zab)]
                                                        # description_wiki
                                                        inc_msg.append(description_wiki)
                                                        keys_url = (sorted(urls_images.keys()))
                                                        logging.debug("keys_url - {0}".format(keys_url))
                                                        # graphs from zabbix
                                                        for ku in keys_url:
                                                            t_time = urls_images[ku][0]
                                                            inc_msg.append('<br>Corresponding graph for the last {0} (UTC):'.format(time_human_format(t_time)))
                                                            inc_msg.append('<br><br><img src="cid:{0}"><br>'.format(ku))
                                                        if trigger_jira and not re.search('^Disable|^disabled|^\s|None|^$', str(trigger_jira), re.IGNORECASE):
                                                            jira_msg = 'Hi!\n\nWe still have  an alert about:\n{0} - {1}\n\nLink to Zabbix {2}.\n\nPlease check.'.format(trigger_name, item_value, url_zab)


                                                            create_jira(jira_user, jira_password, downloaded_images_name['url_time1'], mail_subject, jira_msg, trigger_jira)
                                                            if create_jira_res == 0:
                                                                opened_jira = j_k
                                                                jiras_count = int(mysqlData['jira_count']) + 1
                                                                inc_msg.append('<br>Corresponding <a href={0}>Jira</a> was created.<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{1}</div>'.format(
                                                                        jira_link, time_seconds))
                                                            else:
                                                                inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                        time_seconds))
                                                        else:

                                                            inc_msg.append('<br>Please check.<br><br>Kind regards, <br><b>Your__company   <font color="red"> NOC</font> </b> <br><font color="red">M: </font> +38 (066) 111 1111 <br><font color="red">S: </font> noc_your_company <br><font color="red">W: </font>      www.yoursite.com <br><div style="display:none;">{0}</div>'.format(
                                                                    time_seconds))
                                                        final_inc_msg = ''.join(inc_msg)
                                                        try:
                                                            logging.debug("Id-{0}; recipients: {1}; cc_recipients: {2}".format(trig_id, recipients, cc_recipients))
                                                            logging.info("Email-Id_check - {0}".format(email_id))
                                                            email_inc(final_inc_msg, keys_url, downloaded_images_name, email_id, mail_subject, recipients, cc_recipients)
                                                            for u in keys_url:
                                                                if os.path.isfile(downloaded_images_name[u]):
                                                                    os.remove(downloaded_images_name[u])
                                                                    logging.info("Deleting image: {0}".format(downloaded_images_name[u]))
                                                            if res_email_sent == 0:

                                                                mysql_data(trig_id, jiras_count, opened_jira, email_id, item_value, "0", 'update', '', '', mail_subject)
                                                                logging.info("Adding new info to automations-db and sending final inc message. Id-{0}".format(trig_id))
                                                                time.sleep(5)
                                                                continue
                                                            else:
                                                                logging.error(
                                                                    "Email was NOT send ! Data in DB was not updated. Id - {0}".format(trig_id))
                                                                continue
                                                        except Exception as ex:
                                                            for u in keys_url:
                                                                if os.path.isfile(downloaded_images_name[u]):
                                                                    os.remove(downloaded_images_name[u])
                                                                    logging.info("Removing image {0}".format(downloaded_images_name[u]))
                                                            msg_me = '<br>Hi!<br><br><b><font color="red">Email was not sent !</font></b><br><br>Please check  alerts and send corresponding email if needed.<br>Sometning went wrong with mail-server or script.<br><b>Team</b>- Please check the log file: {0} <br>Error:  {1}'.format(
                                                                log_file, ex)
                                                            msg_log = "Sometning went wrong with email sender: {0}".format(ex)
                                                            me_mail_subject = 'ERROR_automail ' + str(date) + str(
                                                                ' - ') + "Sometning went wrong with email sender" + str(zabbix_location)
                                                            email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                                            time.sleep(2)
                                                            continue
                                                else:
                                                    logging.info("Time difference less than resubmit time. {0}".format(time_difference))
                                                    continue
                                            else:
                                                logging.warning("resubmit string on WIKI is empty")
                                                continue
                                    else:
                                        logging.critical("It seems time on this server is different with time on DB-server."
                                                         "I can't work properly so I'm going to die...")
                                        break
                                else:
                                    logging.info("Trigger is disabled Id-{0}".format(trig_id))
                                    continue
                            except KeyError:
                                msg_me = 'Hi<br><br><font color="red">Email was not sent !</font><br>No Email_Id was found in DB for trigger id={0}<br>'.format(trig_id)
                                msg_log = "No Email_Id was found in DB for trigger Id-{0}".format(trig_id)
                                me_mail_subject = 'ERROR_automail ' + str(date) + str(' - ') + "No Email_Id was found in DB - " + str(zabbix_location)
                                email_to_me(msg_me, me_mail_subject, log_file, date_time_now, msg_log)
                                time.sleep(2)
                                continue

    load_one_by_one(trigger_list, cookies, email_hours_same_thread)

# ------- MAIN loop for load zabbix_location one by one ----------------------------------------------------------------

for zabbix_location in zabbix_hosts:
    if zabbix_location != 'zabbix_pass' and zabbix_location != 'user':
        try:
            main(zabbix_location)
        except Exception as daemon_ex:
            try:
                msg_me = "<br>Hi!<br><br>Email was not sent<br>Exception: {0}<br>It means that corresponding AUTO-emails for Zabbix-{1} were not sent.".format(daemon_ex, zabbix_location)
                msg = MITeamText(msg_me, 'html')
                msg['Subject'] = "ERROR_automail: One thread of Daemon has failed location - Zabbix-" + str(zabbix_location)
                msg['From'] = 'nocteam@test.com'
                msg['To'] = "MONITORING@test.com"
                send = smtplib.SMTP(mail_server_address)
                send.send_message(msg)
                send.close()
                logging.critical("ERROR_automail: One thread of Daemon has failed - Zabbix-{0}".format(zabbix_location))
                continue
            except Exception as me:
                logging.critical("Email_to_me was not sent. Exception: {0}. Subject - 'ERROR_automail: One thread of Daemon has failed - Zabbix-{1}'".format(me, zabbix_location))
                continue
        logging.info("I'm going to rest 10 seconds")
        logging.info("...............................................................................................")
        time.sleep(10)

