import hashlib
import hmac
import requests
import yaml
import re
import json
import sys
import os
from flask import Flask, request, Response

ZH_BASEURL = "https://api.zenhub.io"
ZH_API_VER = "p1"
GH_BASEURL = "https://api.github.com"

app = Flask(__name__)

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
    res = requests.get(zh_req_url, headers={"X-Authentication-Token": app.config["ZENHUB_TOKEN"]})
    for column in res.json()["pipelines"]:
        app.config["zh_column_ids"][column["name"]] = column["id"]


def get_zh_column_id(column_name):
    app.config["zh_column_ids"][column_name] = app.config["zh_column_ids"].get(column_name, "")
    return app.config["zh_column_ids"][column_name]


def move_card_on_zh(repo_id, issue_num, column_name):
    zh_req_url = "{}/{}/repositories/{}/issues/{}/moves".format(ZH_BASEURL,
                                                                ZH_API_VER,
                                                                repo_id,
                                                                issue_num)
    zh_req_data = {"pipeline_id": get_zh_column_id(column_name),
                   "position": "top"}
    zh_req_header = {"X-Authentication-Token": app.config["ZENHUB_TOKEN"],
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
    gh_req_headers = {"Authorization": "token " + app.config["GITHUB_TOKEN"]}
    res = requests.post(gh_req_url, data=json.dumps(gh_req_data), headers=gh_req_headers)
    return res


@app.route('/', methods=['GET'])
def sanity_check():
    return "hello"


@app.route('/from_github', methods=['POST'])
def process_github_request():
    if not validate_github_request(request):  # request is not from github
        return Response(status=406)
    event_name = request.headers.get("X-GitHub-Event")
    payload = request.get_json()
    if payload is None:  # request body is not json
        return Response(status=415)
    try:
        repo_id = get_repo_id_from_gh_req(payload)
        print(repo_id)
    except KeyError:
        # Reqeust passed the security check, but does not contain proper contents 
        # (likely the first "init" delivery)
        return Response(status=200)
    if len(app.config["zh_column_ids"]) == 0:
        cache_zh_column_ids(repo_id)
    if event_name == "issues":
        issue_num = get_num_from_gh_req(payload)
        if payload["action"] == "reopened" and "is_reopened" in app.config:
            print("An issue is re-opened")
            response = move_card_on_zh(repo_id, issue_num, app.config["is_reopened"])
        elif payload["action"] == "closed" and "is_closed" in app.config:
            print("An issue is closed")
            response = move_card_on_zh(repo_id, issue_num, app.config["is_closed"])
    elif event_name == "pull_request":
        issue_num = get_num_from_gh_req(payload)
        if payload["action"] == "opened":
            if len(payload['pull_request']['requested_reviewers']) > 0 and 'pr_revreq' in app.config:
                print("A pull request is opened and review requested")
                response = move_card_on_zh(repo_id, issue_num, app.config["pr_revreq"])
            elif "pr_opened" in app.config:
                print("A pull request is opened")
                response = move_card_on_zh(repo_id, issue_num, app.config["pr_opened"])
        elif payload["action"] == "reopened" and "pr_reopened" in app.config:
            print("A pull request is re-opened")
            response = move_card_on_zh(repo_id, issue_num, app.config["pr_opened"])
        elif payload["action"] == "review_requested" and "pr_revreq" in app.config:
            print("Review requested for a pull request")
            response = move_card_on_zh(repo_id, issue_num, app.config["pr_revreq"])
        elif payload["action"] == "closed":
            if payload["pull_request"]["merged"] and "pr_merged" in app.config:
                print("A pull request is merged")
                response = move_card_on_zh(repo_id, issue_num, app.config["pr_merged"])
            elif not payload["pull_request"]["merged"] and "pr_closed" in app.config:
                print("A pull request is closed without merge")
                response = move_card_on_zh(repo_id, issue_num, app.config["pr_closed"])
    elif event_name == "create":
        if payload["ref_type"] == "branch" and "new_branch" in app.config:
            branch_formatted = re.match(r'([0-9]+)-', payload["ref"])
            if branch_formatted:
                issue_num = branch_formatted.group(1)
                repo_fullname = get_repo_fullname_from_gh_req(payload)
                print("#{} related branch is pushed by `{}`".format(issue_num, payload["sender"]["login"]))
                response = move_card_on_zh(repo_id, issue_num, app.config["new_branch"])
                if response.status_code == 200: 
                    response = assign_issue_to_on_gh(repo_fullname, issue_num, payload["sender"]["login"])
    else:
        return Response(status=200)
    sys.stdout.flush()
    try:
        return response.content, response.status_code, response.headers.items()
    except UnboundLocalError:
        return Response(status=204, response="Request seems not so interesting.")


def validate_github_request(req):
    return req.method == "POST" \
           and hmac.compare_digest(req.headers["X-Hub-Signature"],
                                   "sha1=" + get_sha1(bytearray(app.config["GITHUB_WEBHOOK_SECRET"], "ascii"),
                                                      req.get_data()))


def get_sha1(key, json):
    return hmac.new(key, msg=json, digestmod=hashlib.sha1).hexdigest()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Run the flask app in debugging mode'
    )
    parser.add_argument(
        '-p', '--port',
        default=5000,
        type=int,
        action='store',
        nargs='?',
        help='Set port to listen. Default is 5000. When deployed on heroku, use the env-var $PORT '
    )
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        action='store',
        nargs='?',
        help='A file path to the config YAML file. By default the app will look for `config.yaml` in the working directory. '
    )
    args = parser.parse_args()

    with open(args.config, "r") as config_file:
        config_dict = yaml.load(config_file)
        for k, v in config_dict.items():
            to_pop = []
            if k in ["ZENHUB_TOKEN", "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET"] and (v is None or len(v) == 0):
                from_envvir = os.environ.get(k)
                if from_envvir is None or len(from_envvir) == 0:
                    raise AttributeError(k + " is required but cannot find!")
                else:
                    config_dict[k] = from_envvir
            elif v is None or len(v) == 0:
                to_pop.append(k)
        for k in to_pop:
            config_dict.pop(k)
        app.config.update(config_dict)
        app.config["zh_column_ids"] = {}

    app.run(host='0.0.0.0', port=args.port, debug=args.debug)
