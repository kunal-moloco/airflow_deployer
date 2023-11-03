# airflow_deployer
Create deploy PR automatically from PR#

Arguments:
- `pr_id`: PR index of the merged change that you want to deploy
- `pr_author`: Name of the author that created the above PR
- `pr_deploy_scope`: File where you want to add commit hash (either `prod` or `test`)
- `pr_dag_name`: Name of the DAG folder where commit hash has to be changed
- `repo_path`: Local path to the airflow repo

While all these arguments are required, you can save some or all of these arguments in a file as below:
```
{
    "pr_id": "4655",
    "pr_author": "Hyungsuk Yoon",
    "pr_deploy_scope": "test",
    "pr_dag_name": "install",
    "repo_path": "/Users/kunal/airflow"
}
```
