# AWS Deployment helper script

Deploy a template (YAML or JSON) from a set (or single) configuration files (YAML)

## Usage  

` python deploy_aws.py --config_paths [CONFIG_PATH]... --template_path [TEMPLATE_PATH]`  

Stack Name: Stack name is based on the filepath. Folder paths and file extension are stripped:

`example/s3.cfn.yml` becomes a stack name of `s3` . 

Script will check for an existing stack. If the stack exists, it will attempt to update it, otherwise it will attept to create it.  

Capabilities: Capabilities are determined by the script and added to the create/update command if needed. Credentials invoking the script must have appropriate aws permissions to deploy.

## Example

From the root directory of this repo:

`python deploy_aws.py --config_paths example/s3.config.yml example/svc.config.yml --template_path example/s3.cfn.yml`  