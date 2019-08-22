#!/usr/bin/env python

import boto3
import botocore.exceptions
import json
from yaml import load as yaml_load
import sys
import argparse
import logging
import uuid
import inquirer

def main(args):

    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    
    logging.debug('-MAIN-')
    
    cfn_client = boto3.client('cloudformation')
    
    # Get the config parameters from the specified YAML file. 
    # TODO: Support multiple config file inputs
    configs = get_configs(args.config_paths)
    
    # Generate CloudFormation compliant parameter json structure, determine capabilities needed, and get the template (aws validation function)
    # This function returns:
    # param_json_object: parameters json structure for cfn
    # cfn_capability_requirement: capability requirement
    # cfn_template: the template body
    validation = process_validation(configs,args.template_path,cfn_client, args.sam)
    
    # Deploy to AWS. Will attempt to update if the stack exists, will attempt to create if not.
    deploy_to_aws(args,validation['param_json_object'],validation['cfn_capability_requirement'],validation['cfn_template'],cfn_client,args.env)
    
    # Done.
    return 0

def get_configs(config_paths):
    
    logging.debug('-GET_CONFIGS-')
    logging.info("Loading config file: " + ' '.join(config_paths))
    
    configs = { } # Get configs from yaml file
    
    
    for file_path in config_paths:
        
        if(file_path.find('s3://') == 0):
            try:
                s3_client = boto3.client('s3')
                
                s3_array = file_path.split('/')
                
                bucket = s3_array[2]
                key = file_path.replace('s3://' + bucket + '/','')  
                
                s3_response = s3_client.get_object(
                    Bucket=bucket,
                    Key=key
                )
                
                configs.update(yaml_load(s3_response['Body'].read()))
                
            except Exception as e:
                logging.critical("Failed to load config file: " + file_path)
                logging.critical(e)
            
        else:
            try:
                with open(file_path) as f:
                    configs.update(yaml_load(f))
                    
                logging.info('Config file loaded: ' + file_path)
        
            except Exception as e:
                logging.critical("Failed to load config file: " + file_path)
                logging.critical(e)
    
    logging.debug(configs)
    
    return configs

#def generate_params(configs,template_path,cfn_client):
def process_validation(configs,template_path,cfn_client,sam):
    
    logging.debug('-GENERATE_PARAMS')
    logging.info("Loading template file: " + template_path)
    
    # Get the template based on the file path given
    
    if(template_path.find('s3://') == 0):
        try:
            s3_client = boto3.client('s3')
                    
            s3_array = template_path.split('/')
            
            bucket = s3_array[2]
            key = template_path.replace('s3://' + bucket + '/','')  
            
            s3_response = s3_client.get_object(
                Bucket=bucket,
                Key=key
            )
            
            template = s3_response['Body'].read()
                    
        except Exception as e:
            logging.critical("Failed to load template file: " + template_path)
            logging.critical(e)
            
    else:
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
    response_validate = cfn_client.validate_template(
        TemplateBody=template
    )
    
    logging.debug('response')
    logging.debug(response_validate)
    
    params = [ ]
    
    logging.info('Generate Params')
    
    # Match up the parameters needed by the template with the params provided by the config file
    # and generate the CloudFormation compliant json parameters object structure
    for idx, template_key in enumerate(response_validate['Parameters']):
        
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
        capability = response_validate['Capabilities']
    except: 
        capability = None
        if sam:
            capability = ['CAPABILITY_IAM']
    
    logging.debug(capability)
    
    return { "param_json_object": params, "cfn_capability_requirement": capability, "cfn_template": template }
    
#def deploy_to_aws(config_paths,template_path,params,capability,template,cfn_client,auto_approve):
def deploy_to_aws(args,params,capability,cfn_template,cfn_client,env):
    
    # Boto3 CFN waiters
    waiter_update = cfn_client.get_waiter('stack_update_complete')
    waiter_create = cfn_client.get_waiter('stack_create_complete')
    waiter_change = cfn_client.get_waiter('change_set_create_complete')
    
    logging.info('Generate stackname based on filename')
    
    # Generate the stack-name based on the filename of the template provided. Strip folder path/file extenstions.
    if(env == 'none'): stack_name = args.template_path.split('.')[0].split('/')[-1].upper()
    else: stack_name = args.template_path.split('.')[0].split('/')[-1].upper() + '-' + env.upper()
    config_paths_print = ' '.join(args.config_paths)
    
    logging.debug('Stack name: ' + stack_name)
    logging.debug('Config paths: ' + config_paths_print)
    
    # Generate the boto3 parameters
    stack_params = { }
    stack_params.update(StackName=stack_name)
    stack_params.update(TemplateBody=cfn_template)
    stack_params.update(Parameters=params)
    
    # If there's a capability requirement, add the boto3 param
    if(capability): stack_params.update(Capabilities=capability)
    
    logging.debug('aws cfn args:')
    logging.debug(stack_params)
    
    # Check if the stack exists already
    try:
        logging.info('aws cloudformation describe_stacks')
        
        response_describe = cfn_client.describe_stacks(StackName=stack_name)
        
        logging.debug('response')
        logging.debug(response_describe)
        
    # If not, attempt to create it, wait, exit when complete or error    
    except botocore.exceptions.ClientError as e:
        logging.info('handle describe exception --> create')
        logging.debug(e)
        
        logging.info('Running Cmd: aws cloudformation create_stack')
        
        response_create = cfn_client.create_stack(**stack_params)
        
        logging.debug('response')
        logging.debug(response_create)
        
        print("Creating stack " + stack_name + " from template " + args.template_path + " and config " + config_paths_print)
        
        logging.info('Start create_stack waiter')
        
        waiter_create.wait(StackName=stack_name)
        
        print("Stack created: " + stack_name)
        
        return 0

    # If the template exists, attempt to update. Wait, exit when complete or error
    try:
        logging.info('aws cloudformation create_change_set')
        
        chng_set_uuid = ('CHNG-' + str(uuid.uuid4())).upper()
        
        stack_params.update(ChangeSetName=chng_set_uuid)
        print('Attempting to create change set: ' + chng_set_uuid)
        response_create_chng_set = cfn_client.create_change_set(**stack_params)
        
        waiter_change.wait(ChangeSetName=chng_set_uuid, StackName=stack_name,WaiterConfig={'Delay':5})
        
        if(args.auto_approve == False): change_set = handle_change_set_inq(response_create_chng_set,cfn_client)['val']
        else: 
            print("Change Set Auto-Aproved")
            change_set = 1
            
        if(change_set == -1):
            response_delete_chng_set = cfn_client.delete_change_set(ChangeSetName=chng_set_uuid, StackName=stack_name)
            
            print('Deleted change set. Exiting.')
            
        elif(change_set == 1):
            response_exec_chng_set = cfn_client.execute_change_set(ChangeSetName=chng_set_uuid, StackName=stack_name)
            
            logging.debug('response')
            logging.debug(response_exec_chng_set)
            
            print("Updating stack " + stack_name + " from template " + args.template_path + " and config " + config_paths_print + " with ChangeSet: " + chng_set_uuid )
            
            logging.info('start update_stack waiter')
            
            waiter_update.wait(StackName=stack_name)
            
            print("Stack updated: " + stack_name)

        else:
            print('Skipping change set execution: ' + response_create_chng_set['Id'])
        
    except Exception as e:
        logging.info('handle update exception --> no updates')
        logging.debug(e)
        response = cfn_client.delete_change_set(ChangeSetName=chng_set_uuid, StackName=stack_name)
        print("No updates to be performed on stack " + stack_name + " from template " + args.template_path + " and config " + config_paths_print)
        
        pass
    
    return 0

# Basic command line user input function. No additional pip installs necessary.
# User interaction function only needed if --auto_approve False
def handle_change_set(response,cfn_client):
    
    execute = -2
    
    response_chng_set = cfn_client.describe_change_set(ChangeSetName=response['Id'])
    
    print('')
    print(json.dumps(response_chng_set, indent=6, sort_keys=True, default=str))
    print('')
    
    while((execute != "0") and (execute != "1") and (execute != "-1")):
        execute = raw_input("Select 1 to execute change set, 0 to skip/retain change set, -1 to delete change set: ")
        print(execute)
        
    return { "val": int(execute) }
    
# More user friendly command line input selection. Additional library (inquirer) needed.
# User interaction function only needed if --auto_approve False
def handle_change_set_inq(response, cfn_client):
    
    response_chng_set = cfn_client.describe_change_set(ChangeSetName=response['Id'])
    
    print('')
    print(json.dumps(response_chng_set, indent=6, sort_keys=True, default=str))
    print('')
    
    questions = [
        inquirer.List('selection',
            message="Change Set Selection:",
            choices=['Execute Change Set', 'Cancel & Delete Change Set', 'Cancel & Save Change Set'],
        ),
    ]
    print('')
    ans = inquirer.prompt(questions)
    
    if(ans['selection'] == 'Execute Change Set'): return { "val": 1 }
    elif(ans['selection'] == 'Cancel & Delete Change Set'): return { "val": -1 }
    else: return { "val": 0 }
    
def parse_args():
    
    parser = argparse.ArgumentParser(description='Deploy AWS CloudFormation stacks based on template and config input files')

    parser.add_argument('--config_paths', type=str, nargs='+', help='Filepath to one or more config files (YAML)')
    parser.add_argument('--template_path', type=str, help='Filepath to a single CloudFormation template (YAML or JSON')
    
    parser.add_argument('--auto_approve', type=bool, help='Auto-approve change set', nargs='?', default=False, const=True)
    parser.add_argument('--sam', type=bool, help='Inlude if using SAM', nargs='?', default=False, const=True)
    
    parser.add_argument('--env', type=str, help='Env specifier', nargs='?', default='none')
    
    args = parser.parse_args()
    
    return args

if __name__ == "__main__":
    
    print('Starting AWS deployment...')
    
    args = parse_args()

    main(args)
    
    sys.exit(0)