#!/usr/bin/env python

import boto3
import botocore.exceptions
import json
from yaml import load as yaml_load
import sys
import argparse
import logging
import uuid

def main(config_paths,template_path):

    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    
    logging.debug('-MAIN-')
    
    client = boto3.client('cloudformation')
    
    # Get the config parameters from the specified YAML file. 
    # TODO: Support multiple config file inputs
    configs = get_configs(config_paths)
    
    # Generate CloudFormation compliant parameter json structure, determine capabilities needed, and get the template
    # This function returns:
    # params[0]: parameters json structure for cfn
    # params[1]: capability requirement
    # params[2]: the template body
    params = generate_params(configs,template_path,client)
    
    param_json_object = params[0]
    cfn_capability_requirement = params[1]
    cfn_template = params[2]
    
    # print(params[0])
    # print(params[1])
    # print(params[2])
    
    # Deploy to AWS. Will attempt to update if the stack exists, will attempt to create if not.
    deploy_to_aws(config_paths,template_path,param_json_object,cfn_capability_requirement,cfn_template,client)
    
    # Done.
    return 0

def get_configs(config_paths):
    
    logging.debug('-GET_CONFIGS-')
    logging.info("Loading config file: " + ' '.join(config_paths))
    
    configs = { } # Get configs from yaml file
    
    for file_path in config_paths:
        try:
            with open(file_path) as f:
                configs.update(yaml_load(f))
                
            logging.info('Config file loaded: ' + file_path)
    
        except Exception as e:
            logging.critical("Failed to load config file: " + file_path)
            logging.critical(e)
    
    logging.debug(configs)
    
    return configs

def generate_params(configs,template_path,client):
    
    logging.debug('-GENERATE_PARAMS')
    logging.info("Loading template file: " + template_path)
    
    # Get the template based on the file path given
    try:
        with open (template_path, "r") as file:
            template = file.read()
            
        logging.info('Template file lodaded: ' + template_path)    
        logging.debug(template)    
        
    except Exception as e:
        logging.critical("Failed to load template file: " + template_path)
        logging.critical(e)
        
    
    logging.info('aws cloudformation validate-template')
    
    # Validate template with AWS
    # This will check basic syntax, and return the parameters needed for the template and the capabilities requirement.
    # TODO: Add error handling for invalid template. This assumes valid template
    response = client.validate_template(
            TemplateBody=template
    )
    
    logging.debug('response')
    logging.debug(response)
    
    params = [ ]
    
    logging.info('Generate Params')
    
    # Match up the parameters needed by the template with the params provided by the config file
    # and generate the CloudFormation compliant json parameters object structure
    for idx, template_key in enumerate(response['Parameters']):
        
        param_obj = { }
        
        try:
            param_obj['ParameterKey'] = template_key['ParameterKey']
            param_obj['ParameterValue'] = configs[template_key['ParameterKey']]
            params.append(param_obj)
            logging.debug(param_obj)
        except:
            pass
        
    logging.info('Get Capabilities')
    
    # Get the capability requirement (if exists)
    try:
        capability = response['Capabilities']
    except: 
        capability = None
    
    logging.debug(capability)
    
    return params, capability, template
    
def deploy_to_aws(config_paths,template_path,params,capability,template,client):
    
    # Boto3 CFN waiters
    waiter_update = client.get_waiter('stack_update_complete')
    waiter_create = client.get_waiter('stack_create_complete')
    waiter_change = client.get_waiter('change_set_create_complete')
    
    
    logging.info('Generate stackname based on filename')
    
    # Generate the stack-name based on the filename of the template provided
    stack_name = template_path.split('.')[0].split('/')[-1]
    config_paths_print = ' '.join(config_paths)
    
    logging.debug('Stack name: ' + stack_name)
    logging.debug('Config paths: ' + config_paths_print)
    
    # Generate the boto3 parameters
    stack_params = { }
    stack_params.update(StackName=stack_name)
    stack_params.update(TemplateBody=template)
    stack_params.update(Parameters=params)
    
    # If there's a capability requirement, add the boto3 param
    if(capability): stack_params.update(Capabilities=capability)
    
    logging.debug('aws cfn args:')
    logging.debug(stack_params)
    
    # Check if the stack exists already
    try:
        logging.info('aws cloudformation describe_stacks')
        
        response = client.describe_stacks(StackName=stack_name)
        
        logging.debug('response')
        logging.debug(response)
        
    # If not, attempt to create it, wait, exit when complete or error    
    except botocore.exceptions.ClientError as e:
        logging.info('handle describe exception --> create')
        logging.debug(e)
        
        logging.info('aws cloudformation create_stack')
        
        response = client.create_stack(**stack_params)
        
        logging.debug('response')
        logging.debug(response)
        
        print("Creating stack " + stack_name + " from template " + template_path + " and config " + config_paths_print)
        
        logging.info('start create_stack waiter')
        
        waiter_create.wait(StackName=stack_name)
        
        print("Stack created: " + stack_name)
        
        return 0

    # If the template exists, attempt to update. Wait, exit when complete or error
    try:
        logging.info('aws cloudformation create_change_set')
        
        #response = client.update_stack(**stack_params)
        
        chng_set_uuid = 'a' + str(uuid.uuid4())
        
        stack_params.update(ChangeSetName=chng_set_uuid)
        print('Attempting to create change set: ' + chng_set_uuid)
        response = client.create_change_set(**stack_params)
        
        waiter_change.wait(ChangeSetName=chng_set_uuid, StackName=stack_name,WaiterConfig={'Delay':5})
        
        change_set = handle_change_set(response,client)
            
        if(change_set == -1):
            response = client.delete_change_set(ChangeSetName=chng_set_uuid, StackName=stack_name)
            
            print('Deleted change set. Exiting.')
            
        elif(change_set == 1):
            response = client.execute_change_set(ChangeSetName=chng_set_uuid, StackName=stack_name)
            
            logging.debug('response')
            logging.debug(response)
            
            print("Updating stack " + stack_name + " from template " + template_path + " and config " + config_paths_print + " with ChangeSet: " + chng_set_uuid )
            
            logging.info('start update_stack waiter')
            
            waiter_update.wait(StackName=stack_name)
            
            print("Stack updated: " + stack_name)
                
            
        else:
            print('Skipping change set execution: ' + response['Id'])
            
        sys.exit(1)
        
    except Exception as e:
        logging.info('handle update exception --> no updates')
        logging.debug(e)
        response = client.delete_change_set(ChangeSetName=chng_set_uuid, StackName=stack_name)
        print("No updates to be performed on stack " + stack_name + " from template " + template_path + " and config " + config_paths_print)
        
        pass
    
    return 0
    
def handle_change_set(response,client):
    
    execute = -2
    
    response_chng_set = client.describe_change_set(ChangeSetName=response['Id'])
    
    print('')
    print(json.dumps(response_chng_set, indent=6, sort_keys=True, default=str))
    print('')
    
    while((execute != "0") and (execute != "1") and (execute != "-1")):
        execute = raw_input("Select 1 to execute change set, 0 to skip/retain change set, -1 to delete change set: ")
        print(execute)
        
    return int(execute)
        
    
def parse_args():
    
    parser = argparse.ArgumentParser(description='Deploy AWS CloudFormation stacks based on template and config input files')

    parser.add_argument('--config_paths', type=str, nargs='+', help='Filepath to one or more config files (YAML)')
    parser.add_argument('--template_path', type=str, help='Filepath to a single CloudFormation template (YAML or JSON')
    
    args = parser.parse_args()
    
    return args

if __name__ == "__main__":
    
    print('Starting AWS deployment...')
    
    args = parse_args()
    
    main(args.config_paths,args.template_path)
    
    sys.exit(0)