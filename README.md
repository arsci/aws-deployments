# AWS Deployment helper script

Deploy a template (YAML or JSON) from a set (or single) configuration files (YAML)

## Install

Packages needed can be installed from the requirements file:

`pip install -r requirements.txt --user`

## Example

From the root directory of this repo:

`python deploy_aws.py --config_paths example/s3.config.yml example/svc.config.yml --template_path example/s3.cfn.yml`  

## Help

`python deploy_aws.py -h`

## S3

Config files and templates can be loaded from S3 using standard s3 prefix:

`... --config_paths s3://bucket/object/key.config.yml ...`  
`... --template_path s3://bucket/object/key.cfn.yml...`

## Env

You can include an environment specifier. Env is appended to the stack name (which is a function of the filename).

`--env prod`


## Usage  

` python deploy_aws.py --template_path [TEMPLATE_PATH] --config_paths CONFIG_PATHS [CONFIG_PATHS ...]`  

Stack Name: Stack name is based on the filepath of the template provided. Folder paths and file extension are stripped:

`example/s3.cfn.yml` becomes a stack name of `s3` . 

The script first checks for an existing stack:

If the stack does not exist, the script will attempt to create the stack.

If the stack exists, a change set will be created and the user will be given the JSON change output and the option to execute, cancel (leaving the change set), or delete the change set and exit.

Capabilities: CFN capabilities are determined by the script and added to the create/update command if needed. Credentials invoking the script must have appropriate aws permissions.

### Auto Approve

For use with automated pipelines, adding the flag `--auto_approve` will automatically execute the change set if it is created successfully (no user input required).
