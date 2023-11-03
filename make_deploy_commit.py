"""Make a branch and commit for deployment of a PR change

Usage: python3 -m make_deploy_commit --config_file <path_to_config_file>
Config file format:
{
    "pr_id": "4655",
    "pr_author": "name",
    "pr_deploy_scope": "test",
    "pr_dag_name": "install",
    "repo_path": "/Users/<name>/airflow"
}
"""
import git
import re
import os
import json
import argparse
import logging


def parse_args():
    """Parse command line arguments."""
    config_parser = argparse.ArgumentParser()
    config_parser.add_argument('--config_file', type=str, required=False)
    config_arg, other_args = config_parser.parse_known_args()
    if not config_arg.config_file or not os.path.isfile(config_arg.config_file):
        logging.warning('Config file not found or not specified, will need all arguments from command line')
        defaults_from_config = {}
    else:
        logging.info(f'Using config file for defaults: {config_arg.config_file}')
        with open(config_arg.config_file, 'r') as f:
            defaults_from_config = json.load(f)
    kwarg_builder = lambda x: {'default': defaults_from_config[x]} if x in defaults_from_config else {'required': True}

    other_parser = argparse.ArgumentParser()
    other_parser.add_argument('--pr_id', type=int, **kwarg_builder('pr_id'))
    other_parser.add_argument('--pr_author', type=str, **kwarg_builder('pr_author'))
    other_parser.add_argument('--pr_deploy_scope', choices=['test', 'prod'],
                              **kwarg_builder('pr_deploy_scope'))
    other_parser.add_argument('--pr_dag_name', type=str, **kwarg_builder('pr_dag_name'))
    other_parser.add_argument('--repo_path', type=str, **kwarg_builder('repo_path'))
    return other_parser.parse_args(other_args)


def check_commit(message, pull_request_id):
    """Check if commit message contains pull request id"""
    regex_result = re.findall(r'\(#(\d+)\)', message)
    if len(regex_result) > 0:
        return regex_result[0] == str(pull_request_id)
    return False


def prompt_if_continue(message):
    """Prompt user if they want to continue"""
    response = input(f'<{message}> Do You Want To Continue? (y/n): ')
    if response.lower() == 'y':
        return True
    return False


def find_commit(commit_list, pull_request_id, author_name):
    """Find commit in commit list that matches pull request id"""
    for commit in commit_list:
        if check_commit(commit.summary, pull_request_id):
            if commit.author.name != author_name:
                if prompt_if_continue(f'Commit {commit.hexsha} is not authored by {author_name}'):
                    return commit
            else:
                return commit
    return None


def check_changes_in_dag_only(files_changed, dag_name):
    """Check if all files changed are in dags/<dag_name> directory"""
    for file in files_changed:
        if not (file.startswith('dags/') and file.split('/')[1] == dag_name):
            if prompt_if_continue(f'File {file} is not in dags/{dag_name} directory'):
                continue
            else:
                return False
    return True


def main():
    """main"""
    args = parse_args()
    logging.info(f"args: {args}")

    main_branch_name = 'main'
    deploy_path = os.path.join(args.repo_path, f'deploy_{args.pr_deploy_scope}.json')
    assert os.path.isfile(deploy_path), "Deploy file not found"

    repo = git.Repo(args.repo_path)
    repo.git.checkout(main_branch_name)
    repo.remotes.origin.pull()
    last_10_commits = list(repo.iter_commits(main_branch_name, max_count=10))

    commit = find_commit(last_10_commits, args.pr_id, args.pr_author)
    assert commit is not None, "Commit not found"
    commit_hash = commit.hexsha

    files_changed_in_commit = list(repo.commit(commit_hash).stats.files.keys())
    if not check_changes_in_dag_only(files_changed_in_commit, args.pr_dag_name):
        logging.error('User aborted')
        return

    repo.create_head(f'deploy-{args.pr_id}').checkout()
    logging.info(f'Created branch deploy-{args.pr_id} and checked out')

    with open(deploy_path, 'r') as f:
        data = json.load(f)
        data['version']['dags'][args.pr_dag_name] = commit_hash

    os.remove(deploy_path)
    with open(deploy_path, 'w') as f:
        json.dump(data, f, indent=4)
    logging.info(f'Updated {deploy_path} with commit hash "{commit_hash}" for DAG: {args.pr_dag_name}')

    try:
        repo.git.add(deploy_path)
        repo.git.commit('-m', f'Deploy PR for PR#{args.pr_id}',
                        '-m', f'Deploy #{args.pr_id} with '
                              f'Commit hash: [{commit_hash}](https://github.com/moloco/airflow/commit/{commit_hash})'
                              f'\nAuthor: {args.pr_author}')
    except git.GitCommandError as e:
        print('Possibly pre-commit hook failed, retrying commit')
        repo.git.add(deploy_path)
        repo.git.commit('-m', f'Deploy PR for PR#{args.pr_id}',
                        '-m', f'Deploy #{args.pr_id} with '
                              f'Commit hash: [{commit_hash}](https://github.com/moloco/airflow/commit/{commit_hash})'
                              f'\nAuthor: {args.pr_author}')
    logging.info('Committed changes to deploy file')

    repo.git.push('origin', f'deploy-{args.pr_id}')
    logging.info(f'Pushed changes to remote branch "deploy-{args.pr_id}"')


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    main()
