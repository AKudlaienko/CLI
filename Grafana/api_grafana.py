#!/usr/bin/env python3

import requests
import traceback
import string
import sys
import random

# --------- Custom Variables ------------------
grafana_url = "https://grafana.staging.org"
g_user = "admin"
g_passwd = "admin_passwd"
list_of_admins = ['testuser@test.com']
user_tmp_passwd_lenth = 13
# ---------------------------------------------

headers = {'Accept': 'application/json', 'Content-type': 'application/json'}
s = requests.Session()
s.auth = (g_user, g_passwd)
s.headers.update(headers)
auth = s.get(grafana_url)
users_added_list = []


def generate_temp_passwd(passwd_lenth, chars):
    try:
        return ''.join(random.choice(chars) for _ in range(passwd_lenth))
    except Exception:
        print("def generate_temp_passwd(passwd_lenth, chars)\n{}".format(traceback.format_exc()))
        raise SystemExit(2)


def delete_user(user_id):
    try:
        u_delete = s.delete(grafana_url + '/api/admin/users/:{}'.format(user_id))
        if u_delete.status_code == 200:
            print(u_delete.content)
        else:
            print("Something went wrong!\nRESPONSE CODE: {0}\n{1}".format(u_delete.status_code, u_delete.content))
    except Exception:
        print("\nError:\n{}\n".format(traceback.format_exc()))
        raise SystemExit(2)


def create_user(user_name, user_passwd, user_mail, user_login, admin):
    global users_added_list
    data = {"name": user_name, "email": user_mail, "login": user_login, "password": user_passwd}
    try:
        response = s.post('{}/api/admin/users'.format(grafana_url), json=data)
        if response.status_code == 200:
            user_id = response.json()["id"]
            print("The user: {0}, ID:{1} was created".format(user_mail, user_id))
            if admin is True or user_mail in list_of_admins:
                data = {"isGrafanaAdmin": True}
                u_permission = s.put(grafana_url + '/api/admin/users/:{}/permissions'.format(user_id), json=data)
                if u_permission.status_code == 200:
                    print("Admin access was granted!")
                    users_added_list.append({"login": user_login, "email": user_mail, "password": user_passwd, "admin": True})
                else:
                    print("Critical:\nThe Admin permissions were not granted!")
            else:
                users_added_list.append({"login": user_login, "email": user_mail, "password": user_passwd, "admin": admin})
        else:
            print("Something went wrong!\nRESPONSE CODE: {0}\n{1}\n\nProbably the user exists:\n{2}/admin/users"
                  .format(response.status_code, response.content, grafana_url))
            raise SystemExit(2)
    except Exception:
        print("\nError:\n{}\n".format(traceback.format_exc()))
        raise SystemExit(2)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        for i in str(sys.argv[1]).split(","):
            create_user(i.strip(), generate_temp_passwd(user_tmp_passwd_lenth, string.ascii_letters + string.digits),
                        i.strip(), i.strip(), False)
        print("Users were created:")
        for user in users_added_list:
            print(user)
    elif len(sys.argv) > 2:
        for i in sys.argv[1:]:
            create_user(i.strip(), generate_temp_passwd(user_tmp_passwd_lenth, string.ascii_letters + string.digits),
                        i.strip(), i.strip(), False)
        print("Users were created:")
        for user in users_added_list:
            print(user)
    else:
        print('\nUsage:\n{0} "test11@testmail.com, test31@testmail.com, test44@testmail.com"\nOR\n'
              '{0} "test11@testmail.com" "test31@testmail.com" "test44@testmail.com"\n'.format(sys.argv[0]))

