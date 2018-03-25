#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Usage:  program.py <customer>

"""

from typing import Mapping, Any, List, MutableSequence
import copy
import itertools
import os

import bel.lang.belobj
import bel.lang.bel_specification
import bel.lang.bel_utils as bel_utils
import bel.db.arangodb as arangodb
import bel.utils as utils
import bel.nanopub.files as files

from bel.Config import config

import logging
log = logging.getLogger(__name__)

Edges = MutableSequence[Mapping[str, Any]]


def add_edge(edges: Edges, edge_ast, nanopub_id, edge_type, annotations):
    """Add edge to edges"""

    # TODO Update convert_namespaces_ast to use it instead of convert_namespaces_str -- need lots of changes to that function

    subj_canon = edge_ast.bel_subject.to_string()
    subj_lbl = bel_utils.convert_namespaces_str(subj_canon, decanonicalize=True)

    subj_components = edge_ast.bel_subject.subcomponents(subcomponents=[])

    obj_canon = edge_ast.bel_object.to_string()
    obj_lbl = bel_utils.convert_namespaces_str(obj_canon, decanonicalize=True)

    if edge_ast.bel_object.__class__.__name__ == 'BELAst':  # Nested BEL Assertion
        obj_components = edge_ast.bel_object.bel_subject.subcomponents(subcomponents=[])
        obj_components = edge_ast.bel_object.bel_object.subcomponents(subcomponents=obj_components)
    else:  # Normal BEL Assertion
        obj_components = edge_ast.bel_object.subcomponents(subcomponents=[])

    edge_hash = utils._create_hash(f'{subj_canon} {edge_ast.bel_relation} {obj_canon}')

    # Add edge_dt after creating hash id in edge_iterator
    edge = {
        "edge": {
            "subject": {
                "name": subj_canon,
                "label": subj_lbl,
                "components": subj_components,
            },
            "relation": {
                "relation": edge_ast.bel_relation,
                "edge_hash": edge_hash,
                "nanopub_id": nanopub_id,
                "edge_type": edge_type,
                "subject_canon": subj_canon,
                "subject": subj_lbl,
                "object_canon": obj_canon,
                "object": obj_lbl,
                "annotations": annotations,
            },
            'object': {
                "name": obj_canon,
                "label": obj_lbl,
                "components": obj_components,
            }
        }
    }

    edges.append(copy.deepcopy(edge))
    return edges


# TODO - remove or fix - this stripped out correctly formatted annotations
def enhance_annotations(annotations):
    """Make sure annotations have type and both id and label or delete them"""
    new = []
    for anno in annotations:
        if not anno.get('type', False):
            continue
        elif anno.get('id', False) and anno.get('label', False):
            continue
        elif anno.get('label', False) and not anno.get('id', False):
            anno['id'] = anno['label']
        elif anno.get('id', False) and not anno.get('label', False):
            anno['label'] = anno['id']
        new.append(anno)

    return new


def create_edges(nanopub: Mapping[str, Any], endpoint: str, namespace_targets: Mapping[str, List[str]], rules: List[str] = [], orthologize_target: str = None) -> Edges:
    """Create edges for Nanopub

    Args:
        nanopub (Mapping[str, Any]): nanopub in nanopub_bel schema format
        endpoint (str): BEL.bio API endpoint to use
        rules (List[str]): which computed edge rules to process, default is all,
           look at BEL Specification yaml file for computed edge signature keys,
           e.g. degradation, if any rule in list is 'skip', then skip computing edges
           just return primary_edge
        namespace_targets (Mapping[str, List[str]]): what namespaces to canonicalize
        orthologize_target (str): species to convert BEL into, e.g. TAX:10090 for mouse, default option does not orthologize

    Returns:
        Tuple[List[Mapping[str, Any]], List[Tuple[str, List[str]]]]: (edge list, validation messages) - edge list with edge attributes (e.g. context) and parse validation messages
    """

    # Extract BEL Version and make sure we can process this
    if nanopub['nanopub']['type']['name'].upper() == "BEL":
        bel_version = nanopub['nanopub']['type']['version']
        versions = bel.lang.bel_specification.get_bel_versions()
        if bel_version not in versions:
            log.error(f'Do not know this BEL Version: {bel_version}, these are the ones I can process: {versions}')
            return []
    else:
        log.error(f"Not a BEL Nanopub according to nanopub.type.name: {nanopub['nanopub']['type']['name']}")
        return []

    nanopub_id = nanopub['nanopub'].get('id', None)
    annotations = copy.deepcopy(nanopub['nanopub']['annotations'])
    if orthologize_target:
        annotations = orthologize_context(orthologize_target, annotations)

    # TODO - fix or remove
    # annotations = enhance_annotations(annotations)

    edges = []
    bo = bel.lang.belobj.BEL(bel_version, endpoint)

    for assertion in nanopub['nanopub']['assertions']:
        if assertion['relation']:
            bel_statement = f"{assertion['subject']} {assertion['relation']} {assertion['object']}"
        else:
            bel_statement = assertion['subject']

        bo.parse(bel_statement)
        if not bo.parse_valid:  # Continue processing BEL Nanopub assertions
            log.error(f'Invalid BEL Statement: {bo.validation_messages}')
            continue

        # TODO - canonicalize or orthologize first - does orthologize also canonicalize?
        bo.canonicalize(namespace_targets=namespace_targets)

        if orthologize_target:
            bo.orthologize(orthologize_target)

        edge_type = 'primary'
        if bo.ast.bel_relation:  # Is this a subject only Assertion?
            add_edge(edges, bo.ast, nanopub_id, edge_type, annotations)

        # Computed edges
        computed_edges_ast = []
        if not rules or 'skip' not in rules:
            computed_edges_ast.extend(bo.compute_edges(rules=rules, ast_result=True))

        edge_type = 'computed'
        for edge_ast in computed_edges_ast:
            add_edge(edges, edge_ast, nanopub_id, edge_type, annotations)

    return edges


def orthologize_context(orthologize_target: str, annotations: Mapping[str, Any]) -> Mapping[str, Any]:
    """Orthologize context

    Replace Species context with new orthologize target and add a annotation type of OrthologizedFrom
    """
    pass  # TODO


def edge_iterator(edges=[], edges_fn=None):
    """Yield documents from edge for loading into ArangoDB"""

    for edge in itertools.chain(edges, files.read_edges(edges_fn)):

        subj = copy.deepcopy(edge['edge']['subject'])
        subj_id = str(utils._create_hash_from_doc(subj))
        subj['_key'] = subj_id
        obj = copy.deepcopy(edge['edge']['object'])
        obj_id = str(utils._create_hash_from_doc(obj))
        obj['_key'] = obj_id
        relation = copy.deepcopy(edge['edge']['relation'])

        relation['_from'] = f'nodes/{subj_id}'
        relation['_to'] = f'nodes/{obj_id}'

        relation_id = str(utils._create_hash_from_doc(relation))
        relation['_key'] = relation_id

        relation['edge_dt'] = utils.dt_utc_formatted()  # don't want this in relation_id

        if edge.get('nanopub_id', None):
            if 'metadata' not in relation:
                relation['metadata'] = {}
            relation['metadata']['nanopub_id'] = edge['nanopub_id']

        yield('nodes', subj)
        yield('nodes', obj)
        yield('edges', relation)


def load_edges_into_db(db, edges=[], edges_fn=None, username: str = None, password: str = None):
    """Load edges into ArangoDB"""
    doc_iterator = edge_iterator(edges=edges, edges_fn=edges_fn)

    arangodb.batch_load_docs(db, doc_iterator)


def main():

    (arango_client, edgestore_db) = arangodb.get_client()
    arangodb.delete_edgestore(arango_client)
    (arango_client, edgestore_db) = arangodb.get_client()
    load_edges_into_db(edgestore_db, edges_fn="edges.jsonl.gz")


if __name__ == '__main__':
    # Setup logging
    import logging.config
    module_fn = os.path.basename(__file__)
    module_fn = module_fn.replace('.py', '')

    if config.get('logging', False):
        logging.config.dictConfig(config.get('logging'))

    log = logging.getLogger(f'{module_fn}')

    main()
