import click


@click.command()
@click.option('--dry-run', is_flag=True)
@click.argument('branch')
@click.argument('commit_id')
def run_build_cli(dry_run: bool, branch: str, commit_id: str):
    from app.build import Build
    from app.configuration import Configuration
    from app.runner import Runner

    conf = Configuration.from_file('config.yml', branch, commit_id)
    conf.dry_run = dry_run

    build = Build.from_configuration(conf)
    runner = Runner.from_build(build)
    runner.run()
