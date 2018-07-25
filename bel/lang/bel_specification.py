#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file contains functions to enhance, retrieve and return BEL object specifications.

NOTE !!!!  Have to BEL Spec JSON files if the BEL Spec JSON format is changed here !!!
           Run `make belspec_json`

"""

import glob
import os
import re
import copy
import glob
import requests
import sys
import yaml
import datetime
import json
import itertools
from typing import Mapping, List, Any
import jinja2
import tatsu
import importlib

from bel.Config import config

import logging
log = logging.getLogger(__name__)

# Custom Typing definitions
BELSpec = Mapping[str, Any]


'''
Keys available in enhanced spec_dict:

- version
- notes
- admin
    - 'version_underscored'
    - 'parser_fn'
- relations
    - 'list'
    - 'list_short'
    - 'list_long'
    - 'to_short'
    - 'to_long'
    - 'info'
- functions
    - 'argument_types'
    - 'entity_types'
    - 'info'
    - 'signatures'
    - 'list'
    - 'list_short'
    - 'list_long'
    - 'primary'
        - 'list_short'
        - 'list_long'
    - 'modifier'
        - 'list_short'
        - 'list_long'
    - 'to_short'
    - 'to_long'
- namespaces
    - 'Activity'
        - info
        - list
        - list_short
        - list_long
        - to_short
        - to_long
    - 'ProteinModification'
        - info
        - list
        - list_short
        - list_long
        - to_short
        - to_long
    - 'AminoAcid'
        - info
        - list
        - list_short
        - list_long
        - to_short
        - to_long


- computed_signatures
'''


def get_specification(version: str) -> Mapping[str, Any]:
    """Get BEL Specification

    The json file this depends on is generated by belspec_yaml2json as
    part of the update_specifications function

    Args:
        version: e.g. 2.0.0 where the filename
    """

    spec_dir = config['bel']['lang']['specifications']

    spec_dict = {}

    bel_versions = get_bel_versions()
    if version not in bel_versions:
        log.error('Cannot get unknown version BEL specification')
        return {'error': 'unknown version of BEL'}

    # use this variable to find our parser file since periods aren't recommended in python module names
    version_underscored = version.replace('.', '_')

    json_fn = f'{spec_dir}/bel_v{version_underscored}.json'

    with open(json_fn, 'r') as f:
        spec_dict = json.load(f)

    return spec_dict


def get_bel_versions() -> List[str]:
    """Get BEL Language versions supported

    Get the list of all BEL Language versions supported.  The file this depends
    on is generated by belspec_yaml2json and is kept up to date using
    `make update_ebnf` or `make update_parsers`.  You can also run `belspec_yaml2json`
    directly as it's added as a command by pip install.

    Returns:
        List[str]: list of versions
    """

    spec_dir = config['bel']['lang']['specifications']

    fn = f'{spec_dir}/versions.json'
    with open(fn, 'r') as f:
        versions = json.load(f)

    return versions


def update_specifications():
    """Update BEL specifications

    Collect BEL specifications from Github BELBio BEL Specification folder
    and store in local directory specified in belbio_conf.yaml

    Process all BEL Specifications in YAML into an enhanced JSON version
    and capture all BEL versions in a separate file for quick access.
    """

    spec_dir = config['bel']['lang']['specifications']
    if not os.path.isdir(spec_dir):
        os.mkdir(spec_dir)

    log.info(f'Updating BEL Specifications - stored in {spec_dir}')

    # Collect new specifications from Git repository
    if config['bel']['lang']['specification_github_repo']:
        github_belspec_files(spec_dir)

    # Ensure that files use 'yaml' extension
    files = glob.glob(f'{spec_dir}/*.yml')
    for fn in files:
        new_fn = fn.replace('yml', 'yaml')
        os.rename(fn, new_fn)

    # Convert YAML to enhanced JSON
    files = glob.glob(f'{spec_dir}/*.yaml')
    versions = {}
    for fn in files:
        filename = os.path.basename(fn)

        check_version = filename.replace('bel_v', '').replace('.yaml', '').replace('_', '.')

        json_fn = fn.replace('.yaml', '.json')
        version = belspec_yaml2json(fn, json_fn)

        if version != check_version:
            log.error(f'Version mis-match for {fn} - fn version: {check_version} version: {version}')
        versions[version] = filename

    with open(f'{spec_dir}/versions.json', 'w') as f:
        json.dump(list(set(versions)), f, indent=4)

    # Convert YAML file to EBNF and then parser module

    create_ebnf_parser(files)


def github_belspec_files(spec_dir):
    """Get belspec files from Github repo

        Repo:  https://github.com/belbio/bel_specifications/tree/master/specifications

    """
    repo_url = 'https://api.github.com/repos/belbio/bel_specifications/contents/specifications'
    params = {}
    github_access_token = os.getenv('GITHUB_ACCESS_TOKEN', '')
    if github_access_token:
        params = {"access_token": github_access_token}

    r = requests.get(repo_url, params=params)
    if r.status_code == 200:
        results = r.json()
        for f in results:
            url = f['download_url']
            fn = os.path.basename(url)

            if 'yaml' not in fn and 'yml' in fn:
                fn = fn.replace('yml', 'yaml')

            r = requests.get(url, params=params, allow_redirects=True)
            if r.status_code == 200:
                open(f'{spec_dir}/{fn}', 'wb').write(r.content)
            else:
                sys.exit(f'Could not get BEL Spec file {url} from Github -- Status: {r.status_code}  Msg: {r.content}')
    else:
        sys.exit(f'Could not get BEL Spec directory listing from Github -- Status: {r.status_code}  Msg: {r.content}')


def belspec_yaml2json(yaml_fn: str, json_fn: str) -> str:
    """Enhance BEL specification and save as JSON file

    Load all BEL Specification YAML files and convert to JSON files
    after enhancing them.  Also create a bel_versions.json file with
    all available BEL versions for fast loading.

    Args:
        yaml_fn: original YAML version of BEL Spec
        json_fn: enhanced JSON version of BEL Spec
    Returns:
        str: version of BEL Spec
    """

    try:
        spec_dict = yaml.load(open(yaml_fn, 'r').read())
    except Exception as e:
        log.error('Warning: BEL Specification {yaml_fn} could not be read. Cannot proceed.'.format(yaml_fn))
        sys.exit()

    # admin-related keys
    spec_dict['admin'] = {}
    spec_dict['admin']['version_underscored'] = spec_dict['version'].replace('.', '_')
    spec_dict['admin']['parser_fn'] = yaml_fn.replace('.yaml', '_parser.py')

    # add relation keys list, to_short, to_long
    add_relations(spec_dict)
    # add function keys list, to_short, to_long
    add_functions(spec_dict)
    # add namespace keys list, list_short, list_long, to_short, to_long
    add_namespaces(spec_dict)

    enhance_function_signatures(spec_dict)

    add_function_signature_help(spec_dict)

    with open(json_fn, 'w') as f:
            json.dump(spec_dict, f)

    return spec_dict['version']


def add_function_signature_help(spec_dict: dict) -> dict:
    """Add function signature help

    Simplify the function signatures for presentation to BEL Editor users
    """
    for f in spec_dict['functions']['signatures']:
        for argset_idx, argset in enumerate(spec_dict['functions']['signatures'][f]['signatures']):
            args_summary = ''
            args_list = []
            arg_idx = 0
            for arg_idx, arg in enumerate(spec_dict['functions']['signatures'][f]['signatures'][argset_idx]['arguments']):
                if arg['type'] in ['Function', 'Modifier']:
                    vals = [spec_dict['functions']['to_short'].get(val, spec_dict['functions']['to_short'].get(val)) for val in arg['values']]
                    args_summary += '|'.join(vals) + "()"
                    arg_idx += 1

                    if arg.get('optional', False) and arg.get('multiple', False) is False:
                        args_summary += '?'
                        text = f'Zero or one of each function(s): {", ".join([val for val in arg["values"]])}'
                    elif arg.get('optional', False):
                        args_summary += "*"
                        text = f'Zero or more of each function(s): {", ".join([val for val in arg["values"]])}'
                    else:
                        text = f'One of following function(s): {", ".join([val for val in arg["values"]])}'

                elif arg['type'] in ['NSArg', 'StrArg', 'StrArgNSArg']:
                    args_summary += f'{arg["type"]}'
                    if arg.get('optional', False) and arg.get('multiple', False) is False:
                        args_summary += '?'
                        if arg['type'] in ['NSArg']:
                            text = f'Zero or one namespace argument of following type(s): {", ".join([val for val in arg["values"]])}'
                        elif arg['type'] == 'StrArgNSArg':
                            text = f'Zero or one amespace argument or default namespace argument (without prefix) of following type(s): {", ".join([val for val in arg["values"]])}'
                        else:
                            text = f'Zero or one string argument of following type(s): {", ".join([val for val in arg["values"]])}'
                    elif arg.get('optional', False):
                        args_summary += "*"
                        if arg['type'] in ['NSArg']:
                            text = f'Zero or more namespace arguments of following type(s): {", ".join([val for val in arg["values"]])}'
                        elif arg['type'] == 'StrArgNSArg':
                            text = f'Zero or more namespace arguments or default namespace arguments (without prefix) of following type(s): {", ".join([val for val in arg["values"]])}'
                        else:
                            text = f'Zero or more of string arguments of following type(s): {", ".join([val for val in arg["values"]])}'
                    else:
                        if arg['type'] in ['NSArg']:
                            text = f'Namespace argument of following type(s): {", ".join([val for val in arg["values"]])}'
                        elif arg['type'] == 'StrArgNSArg':
                            text = f'Namespace argument or default namespace argument (without prefix) of following type(s): {", ".join([val for val in arg["values"]])}'
                        else:
                            text = f'String argument of following type(s): {", ".join([val for val in arg["values"]])}'

                args_summary += ', '
                args_list.append(text)

            args_summary = re.sub(', $', '', args_summary)
            spec_dict['functions']['signatures'][f]['signatures'][argset_idx]['argument_summary'] = f'{f}({args_summary})'
            spec_dict['functions']['signatures'][f]['signatures'][argset_idx]['argument_help_listing'] = args_list

            # print(f'{f}({args_summary})')
            # print(args_list)

    return spec_dict


def add_relations(spec_dict: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add relation keys to spec_dict

    Args:
        spec_dict (Mapping[str, Any]): bel specification dictionary

    Returns:
        Mapping[str, Any]: bel specification dictionary with added relation keys
    """

    # Class 'Mapping' does not define '__setitem__', so the '[]' operator cannot be used on its instances
    spec_dict['relations']['list'] = []
    spec_dict['relations']['list_short'] = []
    spec_dict['relations']['list_long'] = []
    spec_dict['relations']['to_short'] = {}
    spec_dict['relations']['to_long'] = {}

    for relation_name in spec_dict['relations']['info']:

        abbreviated_name = spec_dict['relations']['info'][relation_name]['abbreviation']
        spec_dict['relations']['list'].extend((relation_name, abbreviated_name))
        spec_dict['relations']['list_long'].append(relation_name)
        spec_dict['relations']['list_short'].append(abbreviated_name)

        spec_dict['relations']['to_short'][relation_name] = abbreviated_name
        spec_dict['relations']['to_short'][abbreviated_name] = abbreviated_name

        spec_dict['relations']['to_long'][abbreviated_name] = relation_name
        spec_dict['relations']['to_long'][relation_name] = relation_name

    return spec_dict


def add_functions(spec_dict: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add function keys to spec_dict

    Args:
        spec_dict (Mapping[str, Any]): bel specification dictionary

    Returns:
        Mapping[str, Any]: bel specification dictionary with added function keys
    """

    # Class 'Mapping' does not define '__setitem__', so the '[]' operator cannot be used on its instances
    spec_dict['functions']['list'] = []
    spec_dict['functions']['list_long'] = []
    spec_dict['functions']['list_short'] = []

    spec_dict['functions']['primary'] = {}
    spec_dict['functions']['primary']['list_long'] = []
    spec_dict['functions']['primary']['list_short'] = []

    spec_dict['functions']['modifier'] = {}
    spec_dict['functions']['modifier']['list_long'] = []
    spec_dict['functions']['modifier']['list_short'] = []

    spec_dict['functions']['to_short'] = {}
    spec_dict['functions']['to_long'] = {}

    for func_name in spec_dict['functions']['info']:

        abbreviated_name = spec_dict['functions']['info'][func_name]['abbreviation']

        spec_dict['functions']['list'].extend((func_name, abbreviated_name))

        spec_dict['functions']['list_long'].append(func_name)
        spec_dict['functions']['list_short'].append(abbreviated_name)

        if spec_dict['functions']['info'][func_name]['type'] == 'primary':
            spec_dict['functions']['primary']['list_long'].append(func_name)
            spec_dict['functions']['primary']['list_short'].append(abbreviated_name)
        else:
            spec_dict['functions']['modifier']['list_long'].append(func_name)
            spec_dict['functions']['modifier']['list_short'].append(abbreviated_name)

        spec_dict['functions']['to_short'][abbreviated_name] = abbreviated_name
        spec_dict['functions']['to_short'][func_name] = abbreviated_name

        spec_dict['functions']['to_long'][abbreviated_name] = func_name
        spec_dict['functions']['to_long'][func_name] = func_name

    return spec_dict


def add_namespaces(spec_dict):
    """Add namespace convenience keys, list, list_{short|long}, to_{short|long}"""

    for ns in spec_dict['namespaces']:
        spec_dict['namespaces'][ns]['list'] = []
        spec_dict['namespaces'][ns]['list_long'] = []
        spec_dict['namespaces'][ns]['list_short'] = []

        spec_dict['namespaces'][ns]['to_short'] = {}
        spec_dict['namespaces'][ns]['to_long'] = {}

        for obj in spec_dict['namespaces'][ns]['info']:
            spec_dict['namespaces'][ns]['list'].extend([obj['name'], obj['abbreviation']])
            spec_dict['namespaces'][ns]['list_short'].append(obj['abbreviation'])
            spec_dict['namespaces'][ns]['list_long'].append(obj['name'])

            spec_dict['namespaces'][ns]['to_short'][obj['abbreviation']] = obj['abbreviation']
            spec_dict['namespaces'][ns]['to_short'][obj['name']] = obj['abbreviation']

            spec_dict['namespaces'][ns]['to_long'][obj['abbreviation']] = obj['name']
            spec_dict['namespaces'][ns]['to_long'][obj['name']] = obj['name']

            # For AminoAcid namespace
            if 'abbrev1' in obj:
                spec_dict['namespaces'][ns]['to_short'][obj['abbrev1']] = obj['abbreviation']
                spec_dict['namespaces'][ns]['to_long'][obj['abbrev1']] = obj['name']


def enhance_function_signatures(spec_dict: Mapping[str, Any]) -> Mapping[str, Any]:
    """Enhance function signatures

    Add required and optional objects to signatures objects for semantic validation
    support.

    Args:
        spec_dict (Mapping[str, Any]): bel specification dictionary

    Returns:
        Mapping[str, Any]: return enhanced bel specification dict
    """

    for func in spec_dict['functions']['signatures']:
        for i, sig in enumerate(spec_dict['functions']['signatures'][func]['signatures']):
            args = sig['arguments']
            req_args = []
            pos_args = []
            opt_args = []
            mult_args = []
            for arg in args:
                # Multiple argument types
                if arg.get('multiple', False):
                    if arg['type'] in ['Function', 'Modifier']:
                        mult_args.extend(arg.get('values', []))
                    elif arg['type'] in ['StrArgNSArg', 'NSArg', 'StrArg']:
                        # Complex signature has this
                        mult_args.append(arg['type'])

                # Optional, position dependent - will be added after req_args based on order in bel_specification
                elif arg.get('optional', False) and arg.get('position', False):
                    if arg['type'] in ['Function', 'Modifier']:
                        pos_args.append(arg.get('values', []))
                    elif arg['type'] in ['StrArgNSArg', 'NSArg', 'StrArg']:
                        pos_args.append(arg['type'])

                # Optional, position independent
                elif arg.get('optional', False):
                    if arg['type'] in ['Function', 'Modifier']:
                        opt_args.extend(arg.get('values', []))
                    elif arg['type'] in ['StrArgNSArg', 'NSArg', 'StrArg']:
                        opt_args.append(arg['type'])

                # Required arguments, position dependent
                else:
                    if arg['type'] in ['Function', 'Modifier']:
                        req_args.append(arg.get('values', []))
                    elif arg['type'] in ['StrArgNSArg', 'NSArg', 'StrArg']:
                        req_args.append(arg['type'])

            spec_dict['functions']['signatures'][func]['signatures'][i]['req_args'] = copy.deepcopy(req_args)
            spec_dict['functions']['signatures'][func]['signatures'][i]['pos_args'] = copy.deepcopy(pos_args)
            spec_dict['functions']['signatures'][func]['signatures'][i]['opt_args'] = copy.deepcopy(opt_args)
            spec_dict['functions']['signatures'][func]['signatures'][i]['mult_args'] = copy.deepcopy(mult_args)

    return spec_dict


def get_ebnf_template():
    """Get EBNF template from Github belbio/bel_specifications repo"""

    repo_url = 'https://api.github.com/repos/belbio/bel_specifications/contents/resources/bel.ebnf.j2'
    spec_dir = config['bel']['lang']['specifications']

    params = {}
    github_access_token = os.getenv('GITHUB_ACCESS_TOKEN', '')
    if github_access_token:
        params = {"access_token": github_access_token}

    r = requests.get(repo_url, params=params)
    if r.status_code == 200:
        template_url = r.json()['download_url']
    else:
        sys.exit('Could not get EBNF file download url from Github')

    filename = os.path.basename(template_url)
    local_fp = f'{spec_dir}/{filename}'

    r = requests.get(template_url, params=params, allow_redirects=True)
    if r.status_code == 200:
        open(f'{spec_dir}/{filename}', 'wb').write(r.content)
    else:
        sys.exit('Could not download EBNF file from Github -- Status: {r.status_code}  Msg: {r.content}')

    return local_fp


def create_ebnf_parser(files):
    """Create EBNF files and EBNF-based parsers"""

    flag = False
    for belspec_fn in files:
        # Get EBNF Jinja template from Github if enabled
        if config['bel']['lang']['specification_github_repo']:
            tmpl_fn = get_ebnf_template()

        # Check if EBNF file is more recent than belspec_fn
        ebnf_fn = belspec_fn.replace('.yaml', '.ebnf')
        if not os.path.exists(ebnf_fn) or os.path.getmtime(belspec_fn) > os.path.getmtime(ebnf_fn):
            with open(belspec_fn, 'r') as f:
                belspec = yaml.load(f)

            tmpl_dir = os.path.dirname(tmpl_fn)
            tmpl_basename = os.path.basename(tmpl_fn)

            bel_major_version = belspec['version'].split('.')[0]

            env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_dir))  # create environment for template
            template = env.get_template(tmpl_basename)  # get the template

            # replace template placeholders with appropriate variables
            relations_list = [(relation, belspec['relations']['info'][relation]['abbreviation']) for relation in belspec['relations']['info']]
            relations_list = sorted(list(itertools.chain(*relations_list)), key=len, reverse=True)

            functions_list = [(function, belspec['functions']['info'][function]['abbreviation']) for function in belspec['functions']['info'] if belspec['functions']['info'][function]['type'] == 'primary']
            functions_list = sorted(list(itertools.chain(*functions_list)), key=len, reverse=True)

            modifiers_list = [(function, belspec['functions']['info'][function]['abbreviation']) for function in belspec['functions']['info'] if belspec['functions']['info'][function]['type'] == 'modifier']
            modifiers_list = sorted(list(itertools.chain(*modifiers_list)), key=len, reverse=True)

            created_time = datetime.datetime.now().strftime('%B %d, %Y - %I:%M:%S%p')

            ebnf = template.render(functions=functions_list,
                                   m_functions=modifiers_list,
                                   relations=relations_list,
                                   bel_version=belspec['version'],
                                   bel_major_version=bel_major_version,
                                   created_time=created_time)

            with open(ebnf_fn, 'w') as f:
                f.write(ebnf)

            parser_fn = ebnf_fn.replace('.ebnf', '_parser.py')

            parser = tatsu.to_python_sourcecode(ebnf, filename=parser_fn)
            flag = True
            with open(parser_fn, 'wt') as f:
                f.write(parser)

    if flag:
        # In case we created new parser modules
        importlib.invalidate_caches()


def get_function_help(function: str, bel_spec: BELSpec):
    """Get function_help given function name

    This will get the function summary template (argument summary in signature)
    and the argument help listing.
    """

    function_long = bel_spec['functions']['to_long'].get(function)
    function_help = []

    if function_long:
        for signature in bel_spec['functions']['signatures'][function_long]['signatures']:
            function_help.append({
                "function_summary": signature['argument_summary'],
                "argument_help": signature['argument_help_listing'],
                "description": bel_spec['functions']['info'][function_long]['description'],
            })

    return function_help


def main():
    pass
    # import timy
    # with timy.Timer() as timer:
    #     belspec_yaml2json()
    #     print(timer)


if __name__ == '__main__':
    main()

else:
    # If building documents in readthedocs - provide empty config
    if os.getenv('READTHEDOCS', False):
        config = {}
        log.info('READTHEDOCS environment')
    else:
        update_specifications()

