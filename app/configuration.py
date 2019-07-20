import yaml

from app.artifact import Key, Artifact


class Configuration:
    def __init__(self, name, git_url, commit_id, data_path):
        self.name = name
        self.git_url = git_url
        self.commit_id = commit_id
        self.data_path = data_path

        self.dry_run = False

        self.mode = ''
        self.environment = ''

        self.command = None
        self.command_path = None

        self.keys = []
        self.artifacts = []
        self.output_path = None
        self.version = None
        self.version_out = None
        self.version_url = None
        self.version_flavor = None

        self.docker_file = None
        self.docker_tag = None
        self.docker_data_path = None

    @classmethod
    def from_file(cls, filename: str, branch: str, commit_id: str):
        with open(filename, 'r') as f:
            r = yaml.load(f, Loader=yaml.FullLoader)

            # Top level
            name = r['name']
            repo = r['repo']

            if branch not in r['branches']:
                return None

            data_path = 'data/git'
            c = cls(name, repo, commit_id, data_path)

            c.dry_run = 'dry_run' in r and r['dry_run']

            # Output
            output_config = r['output']
            c.output_path = output_config['path']

            # Docker
            docker_config = r['docker']
            c.docker_file = docker_config['file']
            c.docker_tag = docker_config['tag']
            c.docker_data_path = docker_config['data_path']

            # Branches
            branch_config = r['branches'][branch]

            c.mode = branch_config['mode']
            if c.mode not in ('tags', 'hash'):
                raise ValueError('mode must be "tags" or "hash"')
            c.environment = branch_config['environment']

            c.command = branch_config['command']
            c.command_path = branch_config['path']

            keys = branch_config['keys']
            for key in keys:
                c.keys.append(Key(key['from'], key['to']))

            artifacts = branch_config['artifacts']
            for artifact in artifacts:
                c.artifacts.append(Artifact(artifact['from'], artifact['to']))

            c.version_out = branch_config['version_out']
            c.version_url = branch_config['version_url']
            c.version_flavor = branch_config['version_flavor']

        return c
