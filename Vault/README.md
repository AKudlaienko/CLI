# tools
A simple script to build the tree of Vault
###### Requirements

  * Clone repo on your machine
  * Install required libs via python pip3
  * Python version >= 3

---

###### Required libs

* json
* traceback
* urllib3

---

###### What does this script do

It's a simple script to get all existing links from a Vault.
So as a result you'll get a file with links, like a tree.
To make it work you should provide Secret Engine address of vault, like: 'test-env1/' or 'dev/'
Also you should define your own variables in your .bashrc:
```sh
export VAULT_ADDR=https://vault.test.com
export VAULT_TOKEN=4gxxxxx-2zxx-xxxx-xx85-axx34rxx
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export USER_login=confluence_username
export USER_secret=confluence_password
```
Please be patient, it takes time to aggregate all data.

###### Usage
```sh
./tree.py 'test-env1/'
```
---
