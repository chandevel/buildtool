import yaml


class GlobalConfig():
    def __init__(self):
        self.hook_secret: str = ''
        self.github_token: str = ''
        self.github_repo_path: str = ''
        self.log_url: str = ''
        self.log_path: str = ''


def load_config():
    c = GlobalConfig()

    with open('config.yml', 'r') as f:
        r = yaml.load(f, Loader=yaml.FullLoader)

        c.hook_secret = r['hook_secret']
        c.github_token = r['github_token']
        c.github_repo_path = r['github_repo_path']
        c.log_url = r['log']['url']
        c.log_path = r['log']['path']

    return c


global_config: GlobalConfig = load_config()
