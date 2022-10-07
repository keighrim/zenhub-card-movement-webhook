import hashlib
import hmac
import requests
import re
import json
import sys
import os

ZH_BASEURL = "https://api.zenhub.io"
ZH_API_VER = "p1"
GH_BASEURL = "https://api.github.com"
zh_column_ids = {}


def get_repo_id_from_gh_req(payload):
    return payload["repository"]["id"]


def get_repo_fullname_from_gh_req(payload):
    return payload["repository"]["full_name"]


def get_num_from_gh_req(payload):
    if "issue" in payload:
        return payload["issue"]["number"]
    elif "pull_request" in payload:
        return payload["pull_request"]["number"]


def cache_zh_column_ids(repo_id):
    zh_req_url = "{}/{}/repositories/{}/board".format(ZH_BASEURL,
                                                      ZH_API_VER,
                                                      repo_id)
    res = requests.get(zh_req_url, headers={"x-authentication-token": os.environ["zenhubToken"]})
    return {column['name']: column['id'] for column in res.json()["pipelines"]}


def get_zh_column_id(column_name):
    global zh_column_ids
    return zh_column_ids.get(column_name, "")


def move_card_on_zh(repo_id, issue_num, column_name):
    if column_name:
        zh_req_url = "{}/{}/repositories/{}/issues/{}/moves".format(ZH_BASEURL,
                                                                    ZH_API_VER,
                                                                    repo_id,
                                                                    issue_num)
        zh_req_data = {"pipeline_id": get_zh_column_id(column_name),
                       "position": "top"}
        zh_req_header = {"x-authentication-token": os.environ["zenhubToken"],
                         "Content-Type": "application/json"}
        res = requests.post(zh_req_url, data=json.dumps(zh_req_data), headers=zh_req_header)
        return res


def assign_issue_to_on_gh(repo_fullname, issue_num, assignee):
    repo_owner, repo = repo_fullname.split('/')
    gh_req_url = "{}/repos/{}/{}/issues/{}/assignees".format(GH_BASEURL,
                                                             repo_owner,
                                                             repo,
                                                             issue_num)
    gh_req_data = {"assignees": [assignee]}
    gh_req_headers = {"Authorization": "token " + os.environ["githubToken"]}
    res = requests.post(gh_req_url, data=json.dumps(gh_req_data), headers=gh_req_headers)
    return res


def lambda_handler(event, context):
    global zh_column_ids
    if not validate_github_request(event):  # request is not from github
        return {"statusCode": 406}
    event_name = event['headers']["x-github-event"]
    payload = json.loads(event['body'])
    if payload is None:  # request body is not json
        return {"statusCode": 415}
    try:
        repo_id = get_repo_id_from_gh_req(payload)
        print(repo_id)
    except KeyError:
        # Reqeust passed the security check, but does not contain proper contents 
        # (likely the first "init" delivery)
        return {"statusCode": 200}
    zh_column_ids = cache_zh_column_ids(repo_id)
    response = None
    if event_name == "issues":
        issue_num = get_num_from_gh_req(payload)
        if payload["action"] == "reopened" and "isReopened" in os.environ:
            print("An issue is re-opened")
            response = move_card_on_zh(repo_id, issue_num, os.environ["isReopened"])
        elif payload["action"] == "closed" and "isClosed" in os.environ:
            print("An issue is closed")
            response = move_card_on_zh(repo_id, issue_num, os.environ["isClosed"])
    elif event_name == "pull_request":
        issue_num = get_num_from_gh_req(payload)
        if payload["action"] == "opened":
            if len(payload['pull_request']['requested_reviewers']) > 0 and 'prRevreq' in os.environ:
                print("A pull request is opened and review requested")
                response = move_card_on_zh(repo_id, issue_num, os.environ["prRevreq"])
            elif "prOpened" in os.environ:
                print("A pull request is opened")
                response = move_card_on_zh(repo_id, issue_num, os.environ["prOpened"])
        elif payload["action"] == "reopened" and "prReopened" in os.environ:
            print("A pull request is re-opened")
            response = move_card_on_zh(repo_id, issue_num, os.environ["prOpened"])
        elif payload["action"] == "review_requested" and "prRevreq" in os.environ:
            print("Review requested for a pull request")
            response = move_card_on_zh(repo_id, issue_num, os.environ["prRevreq"])
        elif payload["action"] == "closed":
            if payload["pull_request"]["merged"] and "prMerged" in os.environ:
                print("A pull request is merged")
                response = move_card_on_zh(repo_id, issue_num, os.environ["prMerged"])
            elif not payload["pull_request"]["merged"] and "prClosed" in os.environ:
                print("A pull request is closed without merge")
                response = move_card_on_zh(repo_id, issue_num, os.environ["prClosed"])
    elif event_name == "create":
        if payload["ref_type"] == "branch" and "newBranch" in os.environ:
            branch_formatted = re.match(r'([0-9]+)-', payload["ref"])
            if branch_formatted:
                issue_num = branch_formatted.group(1)
                repo_fullname = get_repo_fullname_from_gh_req(payload)
                print("#{} related branch is pushed by `{}`".format(issue_num, payload["sender"]["login"]))
                response = move_card_on_zh(repo_id, issue_num, os.environ["newBranch"])
                if response.status_code == 200: 
                    response = assign_issue_to_on_gh(repo_fullname, issue_num, payload["sender"]["login"])
    else:
        return {"statusCode": 200}
    sys.stdout.flush()
    if response:
        try:
            return {
                "statusCode": response.status_code,
                "headers": response.headers,
                "body": response.content
            }
        except UnboundLocalError:
            return {"statusCode": 204}
    else:
        return {"statusCode": 200}


def validate_github_request(req):
    return hmac.compare_digest(
        req['headers']["x-hub-signature"],
        "sha1=" + get_sha1(bytearray(os.environ["githubWebhookSecret"], "ascii"), bytearray(req['body'], 'utf8'))
    )


def get_sha1(key, json):
    return hmac.new(key, msg=json, digestmod=hashlib.sha1).hexdigest()
