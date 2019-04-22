# zenhub-card-movement-webhook
[![License](https://img.shields.io/github/license/keighrim/zenhub-card-movement-webhook.svg?style=popout-square)](LICENSE) 
[![Version](https://img.shields.io/github/tag/keighrim/zenhub-card-movement-webhook.svg?style=popout-square)](https://github.com/keighrim/zenhub-card-movement-webhook/tags) 

## Features 

This is a A HTTP server written in Python 3 with [flask framework](http://flask.pocoo.org/) to create a webhook between Zenhub and Github that mimics ["automation" features](https://help.github.com/en/articles/configuring-automation-for-project-boards) from the github project.
#### Github automation 
Currently the app implements all of github's features with some exceptions due to limitations of APIs. See this table. 

| Automation | Support? | config-key |
| --- | --- | :---: |
| Add to X when a new issue submitted | `&` | - |
| Move to X when an issue reopend | O | `is_reopened` |
| Add to X when a new PR is open | O | `pr_opened` |
| Move to X when a PR is reopened | O | `pr_reopened` |
| Move to X when a PR gets approved (by reviewers) | `X` | - |
| Move to X when reviews requested on a PR | O | `pr_revreq` |
| Move to X when an issue is closed | `%` | `is_closed` |
| Move to X when a PR is merged | `%` | `pr_merged` |
| Move to X when a PR is closed w/o merging | `%` | `pr_closed` |

* `X` - github API not supported
* `&` - New issues always go to the first column in Zenhub board by default. 
* `%` - Closed issues and PRs will be moved by Zenhub to "Closed" and can't be moved further unless re-opened. 

#### One more thing. 
Additionally, the app supports automated movement + assignment of an issue card when a branch whose name starts with `issueNum-` is newly created. For instance, when a new branch `13-bugfix` pushed, the webhook will move issue #13 card to the designated column (see below) and assign the issue to the pusher of the branch. The config-key for this automation is `new_branch`. Note that the "*assigner*" will be the owner of github access token. That is, in the github issue thread, a message saying `${assigner} assigned ${assignee} ${some_time} ago`, where the assigner is the token owenr and the assignee is the puhser, will show up. So for organizational usage, it is recommended to have a dummy administrative account to appear as the automated assigner.  

## How to set up

### App configuration

1. Edit `config.yaml` file. There are 10 keys in the file that you can configure. 
    * `ZENHUB_TOKEN` : Zenhub board access token. Can obtain [here](https://app.zenhub.com/dashboard/tokens).
    * `GITHUB_TOKEN` : Github access token. See [this](https://help.github.com/en/articles/creating-a-personal-access-token-for-the-command-line) to get one. 
    * `GITHUB_WEBHOOK_SECRET` : A hash key to to compute hashes of requests from github. See [here](https://developer.github.com/webhooks/securing/#setting-your-secret-token) for details. If you set up a multi-repository or cross organization Zenhub board, we need to use the same secret key for all connected github repositories or github organization. 
    * `is_reopened`, `is_closed` , `pr_opened` , `pr_revreq` , `pr_merged` , `pr_closed` , `new_branch` : Fill in with target Zenhub board column (or *pipeline*) names for each automation condition. Don't forget to double-quote names that include spaces. If left empty, the automation conditioned on those will be disabled. 
1. **Be careful not to push your access tokens to a public repository.** If you don't want to use app config file to store access tokens, use system environment variables with the same names. 
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
1. Example command
```
GITHUB_TOKEN=SomeGithubToken ZENHUB_TOKEN=SomeZenhubTokenUsuallyLongerThanGitHubOne python3 app.py -p $PORT
```

### Github and Zenhub configuration 
#### Zenhub side: 
No specific configuration is required. You only need to obtain a access token for the taget board and properly config the app to use it. 
#### Github side
Add a webhook as follows using github web interface or API on repository level or organization level. 
* Payload URL: suffix `/from_github` route after your host and port
* Content type: `applicatino/json`
* Secret: the secret key you use as `GITHUB_WEBHOOK_SECRET`
* events: to minimize traffic load, pick `Branch or tag creation`, `Issue`, `Pull Requests`
    
##### The app only supports a single Zenhub board at a time. In other words, you need to have one instance of the webhook server for one Zenhub board. However, a single Zenhub board can be connect to a multiple github repositories across multiple organizations. in which case you need to hook all repositories (or organizations) to the server.

