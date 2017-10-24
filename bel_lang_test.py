import bel_lang
import pytest
import pprint
import json


class Colors:
    PINK = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

VERSION = '2.0.0'
ENDPOINT = 'http://example.com/endpoint'
# statement_to_parse = 'a(CHEBI:"nitrogen atom")'
# statement_to_parse = 'deg(r(HGNC:MYC))'
# statement_to_parse = 'g(HGNC:CFTR, var("c.1521_1523delCTT"))'
# statement_to_parse = 'act(p(HGNC:AKT1), ma(kin)) increases complex(p(HGNC:SKP2), p(SFAM:"FOXO Family"))'
statement_to_parse = 'p(fusion(HGNC:BCR, "p.1_426", HGNC:JAK2, "p.812_1132"))'


bel_instance = bel_lang.BEL(VERSION, ENDPOINT)
parse_obj = bel_instance.parse(statement_to_parse)
print('{}STATEMENT TO PARSE: {}{}'.format(Colors.RED, statement_to_parse, Colors.END))

comp = bel_instance.computed(parse_obj.ast)

print('{}ALL COMPUTED STATEMENTS AS DICTS: {}'.format(Colors.RED, Colors.END))
for num, computed, in enumerate(comp, start=1):
    print('{}. {}'.format(num, computed))

# print('list of computed edges:\n')
# for c in comp:
#     print('\t', c)

# stmts = B.load('dev/bel2_test_statements.txt', loadn=1, preprocess=True)
#
# for s in stmts:
#     print('\n\n\n\n')
#
#     p = B.parse(s)
#     ast = p.ast
#
#     pprint.pprint(ast)
#     exit()
#
#     c = B.computed(ast)
#
#
# statement = 'p(fus(HGNC:BCR, "p.1_426", HGNC:JAK2, "p.812_1132"))'
# expected = ['p(HGNC:BCR) hasFusion p(fus(HGNC:BCR, "p.1_426", HGNC:JAK2, "p.812_1132"))',
#             'p(HGNC:JAK2) hasFusion p(fus(HGNC:BCR, "p.1_426", HGNC:JAK2, "p.812_1132"))']
# ast = B.parse(statement).ast
# l = B.computed(ast)
#
# pprint.pprint(l)
#
# # assert expected == l
