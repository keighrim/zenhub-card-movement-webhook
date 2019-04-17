# zenhub-card-movement-webhook
[![License](https://img.shields.io/github/license/keighrim/zenhub-card-movement-webhook.svg?style=popout-square)](LICENSE) 

## Features 

* A HTTP server written in Python 3 with flask framework to create a webhook between Zenhub and Github that mimics ["automation" features](https://help.github.com/en/articles/configuring-automation-for-project-boards) in the github project.
Currently the app implements all of github's features with a couple of exceptions. See this table. 

| automation | support | config-key |
| --- | --- | :---: |
| Add to X when a new issue submitted | by Zenhub as default | - |
| Move to X when an issue reopend | O | `is_reopened` |
| Add to X when a new PR is open | O | `pr_opened` |
| Move to X when a PR is reopened | O | `pr_reopened` |
| Move to X when a PR gets approved (by reviewers) | X (github API not supported) | - |
| Move to X when reviews requested on a PR | O | `pr_revreq` |
| Move to X when an issue is closed | O | `is_closed` |
| Move to X when a PR is merged | O | `pr_merged` |
| Move to X when a PR is closed w/o merging | O | `pr_closed` |

* Additionally, the app supports automated movement + assignment of an issue card when a branch whose name starts with `issueNum-` is newly created. For instance, when a new branch `13-bugfix` pushed, the webhook will move issue #13 card to designated column and assign the creator of the branch to the issue. The config-key for this automation is `new_branch`. Lastly, the "*assigner*" will be the owner of github access token. So in organizational usage, it is recommended to create a dummy administrative account to create an access token. 

## How to set up

### App configuration

1. Edit `config.yaml` file. There are 10 keys in the file. You need to give values for
    * `ZENHUB_TOKEN` : Zenhub board access token. Can obtain [here](https://app.zenhub.com/dashboard/tokens).
    * `GITHUB_TOKEN` : Github access token. See [this](https://help.github.com/en/articles/creating-a-personal-access-token-for-the-command-line) to get one. 
    * `GITHUB_WEBHOOK_SECRET` : A hash key to to compute hashes of requests from github. See [here](https://developer.github.com/webhooks/securing/#setting-your-secret-token) for details. If you set up a multi-repository or cross organization zenhub board, we need to use the same secret key for all connected github repositories or github organization. 
    * `is_reopened`, `is_closed` , `pr_opened` , `pr_revreq` , `pr_merged` , `pr_closed` , `new_branch` : Fill in with target Zenhub board column (or *pipeline*) names for each automation condition. Don't forget to double-quote names that include spaces. If left empty, the automation conditioned on the empty keys will be disabled. 
1. **NOTE** Be careful not to push your access tokens to a public repository. If you don't want to use app config file for access tokens, use system environment variables with the same names. 
1. Runtime arguments
```
usage: app.py [-h] [-d] [-p [PORT]] [-c [CONFIG]]

optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           Run the flask app in debugging mode
  -p [PORT], --port [PORT]
                        Set port to listen. Default is 5000. When deployed on
                        heroku, use the env-var $PORT
  -c [CONFIG], --config [CONFIG]
                        A file path to the config YAML file. By default the
                        app will look for `config.yaml` in the working
                        directory.
```

### Github and Zenhub configuration 
1. Zenhub side: 
No specific configuration is required. You only need to obtain a access token for the taget board and properly config the app to use it. 
1. Github side
Add a webhook as follows using github web interface or API on repository level or organization level. 
    * Payload URL: suffix `/from_github` route after your host and port
    * Content type: `applicatino/json`
    * Secret: the secret key you use as `GITHUB_WEBHOOK_SECRET`
    * events: to minimize workload, pick `Branch or tag creation`, `Issue`, `Pull Requests`
1. **NOTE** The app only supports a single Zenhub board at a time. So you need to have one instance of the webhook server for one zenhub board. However, a single zenhub board can be connect to a multiple girhub repositories across multiple organization. So in such a case, you need to hook all repositories (or organizations) to the server that's targeting the connected zenhub board. 

