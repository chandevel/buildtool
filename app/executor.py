import logging
import os.path

import docker
from docker.errors import ContainerError

from app.build import Build


class BuildExecutor:
    @classmethod
    def from_configuration(cls, build: Build):
        return cls(build)

    def __init__(self, build: Build):
        self.build = build
        self.configuration = build.configuration

        self.docker_client = None
        self.image = None

    def setup(self):
        logging.info('[BuildExecutor] running build for {}'.format(self.configuration.commit_id))

        self.docker_client = get_docker()

        try:
            with open(self.configuration.docker_file, 'rb') as docker_file:
                logging.info('[BuildExecutor] docker image setup')
                self.image = self.docker_client.images.build(
                    fileobj=docker_file, tag=self.configuration.docker_tag, rm=True)
        except ContainerError as e:
            raise Exception('Build failed', e)

    def run(self):
        try:
            abs_repo_path = os.path.abspath(self.build.source_path)
            container = self.docker_client.containers.run(
                self.image,
                detach=True,
                volumes={
                    abs_repo_path: {
                        'bind': self.configuration.docker_data_path,
                        'mode': 'rw'
                    }
                },
                command=self.configuration.command,
                working_dir=os.path.join(
                    self.configuration.docker_data_path, self.configuration.command_path)
            )
            build_container = container.attach(stdout=True, stderr=True, stream=True)

            failed = False

            for l in build_container:
                line = l.decode('utf8')

                # Can't figure out why the return status is still 0, for now
                # do this.
                if 'BUILD FAILED' in line:
                    failed = True
                self.build.log(line)

            if failed:
                raise Exception('Build failed, see log.')

        except ContainerError as e:
            raise Exception('Build failed', e)


def get_docker():
    docker_client = docker.from_env()
    try:
        docker_client.info()
    except Exception as e:
        raise Exception('Docker not found: %s' % e)
    return docker_client
