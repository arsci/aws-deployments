# AWS Deployment helper script

Deploy a template (YAML or JSON) from a set (or single) configuration files (YAML)

## Example

From the root directory of this repo:

`python deploy_aws.py --config_paths example/s3.config.yml example/svc.config.yml --template_path example/s3.cfn.yml`  

## Usage  

` python deploy_aws.py --template_path [TEMPLATE_PATH] --config_paths CONFIG_PATHS [CONFIG_PATHS ...]`  

Stack Name: Stack name is based on the filepath of the template provided. Folder paths and file extension are stripped:

`example/s3.cfn.yml` becomes a stack name of `s3` . 

The script first checks for an existing stack:

If the stack does not exist, the script will attempt to create the stack.

If the stack exists, a change set will be created and the user will be given the JSON change output and the option to execute, cancel (leaving the change set), or delete the change set and exit.

Capabilities: CFN capabilities are determined by the script and added to the create/update command if needed. Credentials invoking the script must have appropriate aws permissions.

