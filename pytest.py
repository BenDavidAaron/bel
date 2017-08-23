import belpy
import pytest
from belpy.exceptions import *

SPECIFIED_VERSION = '2.0.0'
SPECIFIED_VERSION_UNDERLINED = '2_0_0'

SPECIFIED_ENDPOINT = 'example-endpoint'

B = belpy.BEL(SPECIFIED_VERSION, SPECIFIED_ENDPOINT)

######################
# INITIAL TEST CASES #
######################


def test_semantic_class_instance():
    assert isinstance(B.semantics, belpy.semantics.BELSemantics)


def test_correct_instantiation():
    assert B.version == SPECIFIED_VERSION
    assert B.endpoint == SPECIFIED_ENDPOINT
    assert B.version_dots_as_underscores == SPECIFIED_VERSION_UNDERLINED

#####################
# SYNTAX TEST CASES #
#####################


def test_extra_right_paren():
    s = 'a(CHEBI:"nitric oxide")) decreases r(HGNC:CFTR, var("c.1521_1523delCTT"))'
    with pytest.raises(MissingParenthesis):
        v_obj = B.validate(s)


def test_extra_left_paren():
    s = 'a((CHEBI:"oxygen atom")'
    with pytest.raises(MissingParenthesis):
        v_obj = B.validate(s)


def test_missing_parens():
    s = 'act(p(MGI:Akt1), ma(kin)) decreases MGI:Cdkn1b'
    v_obj = B.validate(s)
    assert v_obj.valid == False


def test_bad_namespace():
    s = 'abundance(CHEBI:"prostaglandin J2":TEST)'
    v_obj = B.validate(s)
    assert v_obj.valid == False


def test_arg_outside():
    s = 'act(p(HGNC:FOXO1)) ma(tscript)'
    v_obj = B.validate(s)
    assert v_obj.valid == False


def test_no_comma_between_args():
    s = 'act(p(HGNC:FOXO3) ma(tscript)) =| r(HGNC:MIR21)'
    v_obj = B.validate(s)
    assert v_obj.valid == False


def test_no_func_given():
    s = 'act(p(MGI:Akt1), ma(kin)) decreases (MGI:Cdkn1b)'
    v_obj = B.validate(s)
    assert v_obj.valid == False

#######################
# SEMANTIC TEST CASES #
#######################


def test_bad_function():
    s = 'atrocious(CHEBI:"nitric oxide") decreases r(HGNC:CFTR, var("c.1521_1523delCTT"))'
    v_obj = B.validate(s)
    assert v_obj.valid == False

def test_bad_relationship():
    s = 'tloc(p(HGNC:CYCS), fromLoc(MESHCS:Mitochondria), toLoc(MESHCS:Cytoplasm)) hello bp(GOBP:"apoptotic process")'
    v_obj = B.validate(s)
    assert v_obj.valid == False

def test_bad_subject():
    s = 'rnaAbundance(MGI:Mir21, extra)'
    v_obj = B.validate(s)
    assert v_obj.valid == False

def test_bad_object():
    s = 'r(fus(HGNC:TMPRSS2, "r.1_79", HGNC:ERG, "r.312_5034")) association path(SDIS:"prostate cancer", bad_arg)'
    v_obj = B.validate(s)
    assert v_obj.valid == False

##############################
# VALID STATEMENT TEST CASES #
##############################

def test_valid_statements():
    list_of_valid_statements = [
        'example',
        'example',
        'example',
        'example',
        'example',
        'example',
    ]


# stmts = B.load('dev/bel2_test_statements.txt', preprocess=True)
#
# for s in stmts:
#     print('\n\n\n\n')
#
#     print(s)
#     p = B.parse(s)
#     st = B.flatten(p.ast)
#
#     print(st)
#     print(s)
#     assert st == s

# statement = 'a(CHEBI:"nitric oxide") decreases (a(CHEBI:"nitric oxide") decreases (a(CHEBI:"nitric oxide") decreases r(HGNC:CFTR, ' \
#             'var("c.1521_1523delCTT"))))'
# print(statement)
