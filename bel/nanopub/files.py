#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""


"""

import json
import yaml
import re
import copy
from typing import Mapping, Any, List, Iterable, Tuple
import gzip

import logging
log = logging.getLogger(__name__)


def read_nanopubs(fn: str) -> Iterable[Mapping[str, Any]]:
    """Read file and generate nanopubs

    If filename has *.gz, will read as a gzip file
    If filename has *.jsonl*, will parsed as a JSONLines file
    IF filename has *.json*, will be parsed as a JSON file
    If filename has *.yaml* or *.yml*,  will be parsed as a YAML file

    Args:
        filename (str): filename to read nanopubs from

    Returns:
        Generator[Mapping[str, Any]]: generator of nanopubs in nanopub_bel JSON Schema format
    """

    jsonl_flag, json_flag, yaml_flag = False, False, False
    if 'jsonl' in fn:
        jsonl_flag = True
    elif 'json' in fn:
        json_flag = True
    elif re.search('ya?ml', fn):
        yaml_flag = True
    else:
        log.error('Do not recognize nanopub file format - neither json nor jsonl format.')
        return {}

    try:
        if re.search('gz$', fn):
            f = gzip.open(fn, 'rt')
        else:
            f = open(fn, 'rt')

        if jsonl_flag:
            for line in f:
                nanopub = json.loads(line)
                if 'nanopub' in nanopub:
                    yield nanopub
        elif json_flag:
            nanopubs = json.load(f)
            for nanopub in nanopubs:
                if 'nanopub' in nanopub:
                    yield nanopub
        elif yaml_flag:
            nanopubs = yaml.load(f)
            for nanopub in nanopubs:
                if 'nanopub' in nanopub:
                    yield nanopub

    except Exception as e:
        log.error(f'Could not open file: {fn}')


def write_nanopubs(nanopubs: Mapping[str, Any], filename: str, jsonlines: bool = False, gzipflag: bool = False, yaml: bool =False):
    """Write nanopubs to file

    Args:
        nanopubs (Mapping[str, Any]): in nanopubs_bel JSON Schema format
        filename (str): filename to write
        jsonlines (bool): output in JSONLines format?
        gzipflag (bool): create gzipped file?
        yaml (bool): create yaml file?
    """
    pass


def read_edges(fn):

    jsonl_flag, json_flag, yaml_flag = False, False, False
    if 'jsonl' in fn:
        jsonl_flag = True
    elif 'json' in fn:
        json_flag = True
    elif re.search('ya?ml', fn):
        yaml_flag = True
    else:
        log.error('Do not recognize nanopub file format - neither json nor jsonl format.')
        return {}

    try:
        if re.search('gz$', fn):
            f = gzip.open(fn, 'rt')
        else:
            f = open(fn, 'rt')

        if jsonl_flag:
            for line in f:
                edges = json.loads(line)
                for edge in edges:
                    yield edge
        elif json_flag:
            edges = json.load(f)
            for edge in edges:
                yield edge
        elif yaml_flag:
            edges = yaml.load_all(f)
            for edge in edges:
                yield edge

    except Exception as e:
        log.error(f'Could not open file: {fn}')


def write_edges(edges: Mapping[str, Any], filename: str, jsonlines: bool = False, gzipflag: bool = False, yaml: bool = False):
    """Write edges to file

    Args:
        edges (Mapping[str, Any]): in edges JSON Schema format
        filename (str): filename to write
        jsonlines (bool): output in JSONLines format?
        gzipflag (bool): create gzipped file?
        yaml (bool): create yaml file?
    """
    pass


def edges_to_jgf(fn, edges):

    jgf_nodes = []
    jgf_edges = []
    for edge in edges:
        if 'edge' in edge:
            jgf_nodes.append({'id': edge['edge']['subject']['name']})
            jgf_nodes.append({'id': edge['edge']['object']['name']})
            jgf_edges.append({
                'source': edge['edge']['subject']['name'],
                'target': edge['edge']['object']['name'],
                'relation': edge['edge']['relation']['name'],
            })

    with open(fn, 'wt') as f:
        graph = {
            'graph': {
                'label': 'BEL Pipeline Edges',
                'type': 'BEL Edges',
                'nodes': copy.deepcopy(jgf_nodes),
                'edges': copy.deepcopy(jgf_edges),
            }
        }

        f.write("{}\n".format(json.dumps(graph, indent=4)))


def main():
    pass


if __name__ == '__main__':
    main()
