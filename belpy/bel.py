import importlib
import os

from tatsu.exceptions import FailedParse
from tatsu.ast import AST

import sys

sys.path.append('../')

from belpy.semantics import BELSemantics
from belpy.tools import TestBELStatementGenerator, ValidationObject, ParseObject
from belpy.tools import preprocess_bel_line, handle_syntax_error, decode
from belpy.exceptions import *


class BEL(object):
    """The summary line for a class docstring should fit on one line.

    If the class has public attributes, they may be documented here
    in an ``Attributes`` section and follow the same formatting as a
    function's ``Args`` section. Alternatively, attributes may be documented
    inline with the attribute's declaration (see __init__ method below).

    Properties created with the ``@property`` decorator should be documented
    in the property's getter method.

    Attributes:
        attr1 (:obj:`str`): Description of `attr1`.
        attr2 (:obj:`int`, optional): Description of `attr2`.

    """

    def __init__(self, version: str, endpoint: str):
        """Example of docstring on the __init__ method.

        The __init__ method may be documented in either the class level
        docstring, or as a docstring on the __init__ method itself.

        Either form is acceptable, but the two should not be mixed. Choose one
        convention to document the __init__ method and be consistent with it.

        Note:
            Do not include the `self` parameter in the ``Args`` section.

        Args:
            version (str): BEL language version
            endpoint (str): URI of TermStore endpoint

            version (:obj:`str`): BEL language version
            endpoint (:obj:`str`): URI of TermStore endpoint

        """
        self.version = version
        self.endpoint = endpoint

        self.version_dots_as_underscores = version.replace('.', '_')
        self.semantics = BELSemantics()

        cur_dir_name = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
        parser_dir = '{}.versions.parser_v{}'.format(cur_dir_name, self.version_dots_as_underscores)

        try:
            imported = importlib.import_module(parser_dir)
            self.parser = imported.BELParser()
        except Exception as e:
            raise NoParserFound(version)


    def parse(self, statement: str, strict: bool = False):
        """
        Parses a BEL statement given as a string and returns a ParseObject, which contains an abstract syntax tree (
        AST) if the statement is valid. Else, the AST attribute is None and there will be exception messages in
        ParseObject.error and ParseObject.visual_err.

        Args:
            statement (str): BEL statement
            strict (bool): specify to use strict or loose parsing; defaults to loose

        Returns:
            ParseObject: The ParseObject which contain either an AST or error messages.
        """

        ast = None
        error = None
        err_visual = None

        if statement == '':
            error = 'Please include a valid BEL statement.'
            return ParseObject(ast, error, err_visual)

        statement = preprocess_bel_line(statement)

        try:
            ast = self.parser.parse(statement, rule_name='start', semantics=self.semantics, trace=False,
                                    parseinfo=False)
        except FailedParse as e:
            error, err_visual = handle_syntax_error(e)
        except Exception as e:
            print(e)
            print(type(e))

        return ParseObject(ast, error, err_visual)

    def stmt_components(self, statement: str):
        """
        Returns the components of a BEL statement as values within a dictionary under the keys 'subject',
        'relationship', and 'object'.

        Args:
            statement (str): BEL statement
            version (str): language version

        Returns:
            dict: The dictionary that contains the components as its values.
        """

        components_dict = dict.fromkeys(['object', 'relationship', 'subject'])
        p = self.parse(statement)
        ast = p.ast

        if ast is None:
            components_dict['object'] = None
            components_dict['relationship'] = None
            components_dict['subject'] = None
            print(p.error)
            print(p.err_visual)
        else:
            components_dict['object'] = ast.get('object', None)
            components_dict['relationship'] = ast.get('relationship', None)
            components_dict['subject'] = ast.get('subject', None)

        return components_dict

    def ast_components(self, ast: AST):
        """
        Returns the components of a BEL AST as values within a dictionary under the keys 'subject', 'relationship',
        and 'object'.

        Args:
            ast (AST): BEL AST

        Returns:
            dict: The dictionary that contains the components as its values.
        """

        components_dict = {}
        components_dict['subject'] = ast.get('subject', None)

        if ast.get('relationship', None) is not None:
            components_dict['object'] = ast.get('object', None)
            components_dict['relationship'] = ast.get('relationship', None)

        return components_dict

    def _create(self, count: int = 1, max_params: int = 3):
        """
        Creates a specified number of invalid BEL statement objects for testing purposes.

        Args:
            count (int): the number of statements to create; defaults to 1
            max_params (int): max number of params each function can take (a large number may exceed recursive depth)

        Returns:
            list: A list of BEL statement objects.
        """

        list_of_bel_stmt_objs = []

        # if user specifies < 1 test statements, do as he/she wishes
        if count < 1:
            return list_of_bel_stmt_objs

        generator = TestBELStatementGenerator(version=self.version)

        for _ in range(count):  # each loop makes one invalid statement
            s = generator.make_statement(max_params)
            list_of_bel_stmt_objs.append(s)

        return list_of_bel_stmt_objs

    def flatten(self, ast: AST):
        """
        Takes an AST and flattens it into a BEL statement string.

        Args:
            ast (AST): BEL AST

        Returns:
            str: The string generated from the AST.
        """
        s = ast.get('subject', None)
        r = ast.get('relationship', None)
        o = ast.get('object', None)

        if r is None:  # if no relationship, this means only subject is present
            sub = decode(s)
            final = '{}'.format(sub)
        else:  # else the full form BEL statement with subject, relationship, and object are present
            sub = decode(s)
            obj = decode(o)
            final = '{} {} {}'.format(sub, r, obj)

        return final

    def load(self, filename: str, loadn: int = -1, preprocess: bool = False):
        """
        Reads a text file of BEL statements separated by newlines, and returns an array of the BEL statement strings.

        Args:
            filename (str): location/name of the text file
            loadn (int): how many statements to load from the file. If unspecified, all are loaded
            preprocess (bool): denote whether or not to run each statement through the preprocessor

        Returns:
            list: The list of statement strings.
        """
        stmts = []

        f = open(filename)
        lcount = 0

        for line in f:

            if lcount == loadn:  # once number of lines processed equals user specified, then stop
                break

            if preprocess:
                line = preprocess_bel_line(line)
            else:
                line = line.strip()

            stmts.append(line)
            lcount += 1

        f.close()

        return stmts

    def validate(self, statement: str, version: str = '2.0.0', strict: bool = False):
        """
        Validates a BEL statement and returns a ValidationObject.

        Args:
            statement (str): BEL statement
            strict (bool): specify to use strict or loose parsing; defaults to loose

        Returns:
            ValidationObject: The ValidationObject which contain either an AST or error messages, and valid boolean.

        """

        # TODO: strict/loose validation
        p = self.parse(statement)

        if p.ast is None:
            valid = False
        else:
            valid = True

        return ValidationObject(p.ast, p.error, p.err_visual, valid)

    def suggest(self, partial: str, value_type: str):
        """
        Takes a partially completed function, modifier function, or a relationship and suggest a fuzzy match out of
        all available options.

        Args:
            partial (str): the partial string
            value_type (str): value type (function, modifier function, or relationship; makes sure we match with
            right list)

        Returns:
            list: A list of suggested values.
        """

        suggestions = []
        # TODO: get the following list of things - initialize YAML into this library so we can grab all funcs,
        # mfuncs, and r.
        if value_type == 'function':
            suggestions = []

        elif value_type == 'mfunction':
            suggestions = []

        elif value_type == 'relationship':
            suggestions = []

        else:
            suggestions = []

        return suggestions

    def canonicalize(self, ast: AST):
        # TODO: this definition
        """
        Takes an AST and returns a canonicalized BEL statement string

        Args:
            ast (AST): BEL AST

        Returns:
            str: The canonicalized string generated from the AST.
        """

    def computed(self, ast: AST):
        # TODO: this definition
        """
        Takes an AST and computes all canonicalized edges

        Args:
            ast (AST): BEL AST

        Returns:
            list:  List of canonicalized computed edges to load into the EdgeStore.
        """
