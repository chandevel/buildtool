import datetime
import json
import os.path
import re
import shutil
import sys

import docker
import yaml
from docker.errors import ContainerError
from git import Repo, GitCommandError


class Configuration:
    def __init__(self, name, git_url, branch, repo_path):
        self.name = name
        self.git_url = git_url
        self.branch = branch
        self.repo_path = repo_path

        self.dry_run = False

        self.mode = ''

        self.command = None
        self.command_path = None

        self.keys = []
        self.artifacts = []
        self.output_path = None
        self.version = None
        self.version_out = None
        self.version_url = None
        self.version_flavor = None

        self.sha = None
        self.tag = None

        self.docker_file = None
        self.docker_tag = None
        self.docker_repo_path = None


class Key:
    def __init__(self, from_file, to_file):
        self.from_file = from_file
        self.to_file = to_file


class Artifact:
    def __init__(self, from_file, to_file):
        self.from_file = from_file
        self.to_file = to_file


def load_configuration(filename, branch):
    with open(filename, 'r') as f:
        r = yaml.load(f)

        # Top level
        name = r['name']
        repo = r['repo']

        if branch not in r['branches']:
            return None

        repo_path = os.path.join('data', 'git', name)
        c = Configuration(name, repo, branch, repo_path)

        c.dry_run = 'dry_run' in r and r['dry_run']

        # Output
        output_config = r['output']
        c.output_path = output_config['path']

        # Docker
        docker_config = r['docker']
        c.docker_file = docker_config['file']
        c.docker_tag = docker_config['tag']
        c.docker_repo_path = docker_config['repo_path']

        # Branches
        branch_config = r['branches'][branch]

        c.mode = branch_config['mode']
        if c.mode not in ('tags', 'hash'):
            raise ValueError('mode must be "tags" or "hash"')

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


def process_repo(repo, conf):
    conf.sha = repo.head.commit.hexsha
    tagref = next((tag for tag in repo.tags if tag.commit == repo.head.commit), None)
    if tagref:
        conf.tag = str(tagref)

    for key in conf.keys:
        from_file = key.from_file
        to_file = key.to_file

        shutil.copy(
            os.path.join(from_file),
            os.path.join(conf.repo_path, to_file)
        )


def gather_repo(conf):
    print('gathering code')

    try:
        path = conf.repo_path
        try:
            # Create if nonexistent
            os.makedirs(path)
            repo = Repo.clone_from(conf.git_url, path)
        except FileExistsError:
            # Reuse if exists
            repo = Repo(path)

        # Reset to branch
        repo.remote().fetch()
        repo.head.reset(index=True, working_tree=True)
        repo.git.checkout(conf.branch)
        repo.git.pull('origin', conf.branch)
    except GitCommandError as e:
        print(e.stdout, e.stderr)
        raise e

    return repo


def execute_build(repo, conf, docker_client):
    print('running build for {}/{}'.format(conf.branch, conf.sha))

    with open(conf.docker_file, 'rb') as docker_file:
        print('docker image setup')
        image = docker_client.images.build(
            fileobj=docker_file, tag=conf.docker_tag, rm=True)

        repo_absolute_path = os.path.abspath(conf.repo_path)

        try:
            container = docker_client.containers.run(
                image,
                detach=True,
                volumes={
                    repo_absolute_path: {
                        'bind': conf.docker_repo_path,
                        'mode': 'rw'
                    }
                },
                command=conf.command,
                working_dir=os.path.join(
                    conf.docker_repo_path, conf.command_path)
            )
            a = container.attach(stdout=True, stderr=True, stream=True)
            for l in a:
                print(l.decode('utf8'), end='')

        except ContainerError as e:
            raise Exception('Build failed', e)


def process_artifacts(repo, conf):
    os.makedirs(conf.output_path, exist_ok=True)

    if conf.mode == 'hash':
        conf.version = conf.sha[:8]
    elif conf.mode == 'tags':
        conf.version = conf.tag

    for artifact in conf.artifacts:
        version = conf.version

        from_file = artifact.from_file
        to_file = artifact.to_file.replace('%v', version)

        shutil.copy(
            os.path.join(conf.repo_path, from_file),
            os.path.join(conf.output_path, to_file)
        )


def get_data_from_git_message(message):
    changelog = ''

    m = re.search(r'^CHANGELOG:[\r\n]([\s\S]+)[\r\n]{2}', message, re.M)
    if m:
        changelog = m.group(1)

    version_code = None
    m = re.search(r'^VERSIONCODE:[\r\n]([\d]+)[\r\n]', message, re.M)
    if m:
        version_code = int(m.group(1))

    return changelog, version_code


def write_version(repo, conf):
    message = '<h2>Clover update ready</h2>A new Clover version is available.'

    changelog, version_code = get_data_from_git_message(repo.head.commit.message)
    if changelog:
        message += '\n\nChangelog:\n' + changelog

    message = message.replace('\n', '<br>')

    with open(conf.version_out, 'w') as f:
        url = conf.version_url.replace('%v', conf.version)

        message = {
            'type': 'update',
            'date': datetime.datetime.today().strftime('%Y-%m-%dT%H:%M:%S'),
            'message_html': message,

            'apk': {
                conf.version_flavor: {
                    'url': url
                }
            }
        }

        if conf.mode == 'hash':
            message['hash'] = conf.sha[:8]
        elif conf.mode == 'tags':
            message['code'] = version_code

        version = {
            'api_version': 1,
            'messages': [message],
            'check_interval': 432000000
        }

        json.dump(version, f, indent=4)


def run_with_configuration(conf: Configuration):
    docker_client = get_docker()

    repo = gather_repo(conf)
    process_repo(repo, conf)
    if conf.mode == 'tags' and not conf.tag:
        print('no tag, aborting')
        return

    if conf.dry_run:
        print('dry_run execute_build')
    else:
        execute_build(repo, conf, docker_client)

    process_artifacts(repo, conf)
    write_version(repo, conf)


def get_docker():
    docker_client = docker.from_env()
    try:
        docker_client.info()
    except Exception as e:
        raise Exception('Docker not found: %s' % e)
    return docker_client


def run(branch):
    conf = load_configuration('config.yml', branch)
    # If a configuration exists for the branch.
    if conf:
        run_with_configuration(conf)


if __name__ == '__main__':
    run('master')
