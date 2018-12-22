#!/usr/bin/env python3


import json
import traceback
import urllib3
import os
import sys
import re
import random
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------- Custom Variables -------------------------------------------------
wiki_base_url = "https://confluence.test.my"
""" Page ID on the Confluence """
wiki_page_id = "1182352632"
""" Page name on the Confluence """
wiki_page_title = "[DEV]Tree"
""" Page space on the Confluence """
wiki_space_key = "DEV"
request_timeout = 10.0
request_retries = 2
# ---------------------------------------------------------------------------------------------------

wiki_page_url = wiki_base_url + "/rest/api/content/" + str(wiki_page_id)
api_token = os.environ['VAULT_TOKEN']
api_url_base = os.environ['VAULT_ADDR'] + "/v1/"
user_l = os.environ['USER_login']
user_x = os.environ['USER_secret']

payload = {'--request': 'LIST'}
api_headers = {'Content-Type': 'application/json',
               'X-Vault-Token': '{}'.format(api_token)}
v_file = os.getenv('HOME') + "/vault_map.txt"
final_urls_raw_lists = []


def geturls_lists(api_url, api_headers, api_req_type):
    try:
        api_url = re.sub("\s+", '%20', api_url)
        http = urllib3.PoolManager()
        response = http.request(api_req_type, api_url, headers=api_headers, timeout=request_timeout, retries=request_retries)
        if response.status == 200 and response is not None:
            raw_lists = json.loads(response.data.decode('utf-8'))['data']['keys']
            return raw_lists
        elif response.status == 400:
            print("\n{} - Bad Request\nThe server cannot or will not process the request due to an apparent client error "
                  "(e.g., malformed request syntax, size too large, invalid request message framing, or deceptive "
                  "request routing).\n".format(response.status))
            return 1
        elif response.status == 401:
            print("\n{} - Unauthorized\n".format(response.status))
            return 1
        elif response.status == 403:
            print("\n{} - Forbidden\nThe request was valid, but the server is refusing action. The user might not have "
                  "the necessary permissions for a resource, or may need an account of some sort.\nAlso check if your TOKEN is valid\n".format(response.status))
            return 1
        elif response.status == 404:
            print("\n{} - Not Found\nThe requested resource could not be found !\n".format(response.status))
            return 1
        else:
            print("\nERROR\n\nResponse status-code: {}\n".format(response.status))
            return 1
    except Exception:
        print("\nERROR: \n{}".format(traceback.format_exc()))
        raise SystemExit(2)


def sort_elements(urls_raw_lists, headers, vault_eng_url):
    x = 1
    while x == 1:
        x = 0
        for element in urls_raw_lists:
            sys.stdout.write("\r{}".format(random.choice([">>", "   >>"])))
            sys.stdout.flush()

            base_elem = element
            if re.search(".*/$", element):
                x = 1
                urls_raw_lists.remove(base_elem)
                element = api_url_base + "{}metadata/".format(vault_eng_url) + str(element)
                elements = geturls_lists(element, headers, 'LIST')
                if type(elements) is not int:
                    for e in elements:
                        urls_raw_lists.append(str(base_elem) + str(e))
                else:
                    print("\nFailed to get data for: '{}'".format(element))
    return urls_raw_lists


def create_html_content(urls_list, eng_address):
    first_level_cat = []
    other = []
    html_page = ''' '''
    html_page += '''<pre>To form a correct link use the next pattern: (Engine + Address) as a result: <i>test-env1/Amazon S3/credentials</i></pre>'''
    html_page += '''<pre><b> Engine: {} </b></pre>'''.format(eng_address)
    for i in urls_list:
        if len(i.split("/")) > 2:
            category = i.split("/")[:2]
            category = '/'.join(category) + "/"
            if re.search(".*/$", str(category)):
                first_level_cat.append(category)
        else:
            other.append(i)
    first_level_cat = list(dict.fromkeys(first_level_cat))

    for level in first_level_cat:
        html_page += '''<pre><b>- {}</b></pre>'''.format(level)
        for l_url in urls_list:
            if re.match(str(level), l_url):
                html_page += '''<pre><p>   \__ {}</p></pre>'''.format(l_url)
    for o_url in other:
        html_page += '''<pre><p>- {}</p></pre>'''.format(o_url)

    return html_page


def update_confluence_page(wiki_url, page_id, html_data):
    wiki_http = urllib3.PoolManager()
    wiki_headers = urllib3.util.make_headers(basic_auth='{0}:{1}'.format(user_l, user_x))
    wiki_headers.update({'Content-Type': 'application/json'})
    wiki_info = wiki_http.request('GET', wiki_url, headers=wiki_headers, timeout=request_timeout,
                                  retries=request_retries)
    if wiki_info.status == 200 and wiki_info is not None:
        wiki_info_raw_data = json.loads(wiki_info.data.decode('utf-8'))
        wiki_info_version_n_old = wiki_info_raw_data['version']['number']
    else:
        print("\n  ERROR\n* Can't get important info regarding the page: {}\n".format(wiki_page_title))
        raise SystemExit(2)

    if wiki_info_version_n_old:
        wiki_info_version_n = wiki_info_version_n_old + 1
        wiki_new_data = {"id": page_id, "type": "page", "title": wiki_page_title, "space": {"key": wiki_space_key},
                         "body": {"storage": {"value": html_data, "representation": "storage"}},
                         "version": {"number": wiki_info_version_n}}
        wiki_encoded_data = json.dumps(wiki_new_data)
        wiki_update_info = wiki_http.request('PUT', wiki_url, headers=wiki_headers, body=wiki_encoded_data,
                                             timeout=request_timeout, retries=request_retries)
        print(wiki_update_info.status)
        if wiki_update_info.status == 200:
            print("Page: {0}, was updated.\n".format(wiki_page_title))


def get_all_data(api_url_base, headers):
    global final_urls_raw_lists
    api_vault_eng_url = ""
    if len(sys.argv) == 2:
        if sys.argv[1] and len(sys.argv[1]) > 2:
            api_vault_eng_url = str(sys.argv[1])
    else:
        print("\nPlease provide Secrets Engines address of vault, like: 'test-env1/' or 'staging/'\n")
        print("\nUSAGE:\n{} 'test-env1/''\n".format(sys.argv[0]))
        raise SystemExit(2)
    try:
        print("\nAggregating data")
        final_urls_raw_lists = geturls_lists(api_url_base + "{}metadata/".format(api_vault_eng_url), headers, 'LIST')
        final_urls_raw_lists = sort_elements(final_urls_raw_lists, headers, api_vault_eng_url)
        print("Data processing finished. Trying to write info in the file: {}".format(v_file))

        if os.path.exists(v_file):
            open(v_file, 'w').close()
        for row in final_urls_raw_lists:
            with open(v_file, 'a+') as v_file_w:
                v_file_w.write("\n{}".format(api_vault_eng_url) + str(row))
        #answer_wiki_page_update = input("\nDo you want to update the page on the Confluence: [Yes|No] ")
        #if re.match("Y|yes", answer_wiki_page_update, re.IGNORECASE):
        try:
            update_confluence_page(wiki_page_url, wiki_page_id, create_html_content(final_urls_raw_lists, api_vault_eng_url))
        except Exception:
            print("Error:\n{}".format(traceback.format_exc()))
            raise SystemExit(2)

        print("Success.\nAll info you can find in the file: {}\nGood luck.\n".format(v_file))
    except Exception:
        print("\nERROR !!!\nException: {}".format(traceback.format_exc()))
        raise SystemExit(2)


if __name__ == "__main__":
    get_all_data(api_url_base, api_headers)





