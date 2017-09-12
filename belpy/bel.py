import importlib
import os
import pprint
import sys

import yaml
from tatsu.ast import AST
from tatsu.exceptions import FailedParse

from belpy.exceptions import NoParserFound
from belpy.semantics import BELSemantics
from belpy.tools import ValidationObject, ParseObject
from belpy.tools import preprocess_bel_line, handle_syntax_error, decode, compute, create_invalid, func_name_translate, \
    get_all_relationships, get_all_function_signatures, get_all_computed_sig_functions

sys.path.append('../')


class BEL(object):

    def __init__(self, version: str, endpoint: str):

        self.version = version
        self.endpoint = endpoint

        # use this variable to find our parser file since periods aren't recommended in file names
        self.version_dots_as_underscores = version.replace('.', '_')

        # each instance also instantiates a BELSemantics object used in parsing statements
        self.semantics = BELSemantics()

        # get the current directory name, and use that to find the version's parser file location
        cur_dir_name = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
        parser_dir = '{}.versions.parser_v{}'.format(cur_dir_name, self.version_dots_as_underscores)

        # use importlib to import our parser (a .py file) and set the BELParse object as an instance variable
        try:
            imported_parser_file = importlib.import_module(parser_dir)
            self.parser = imported_parser_file.BELParser()
        except Exception as e:
            # if not found, we raise the NoPar  serFound exception which can be found in belpy.exceptions
            raise NoParserFound(version)

        # try to load the version's YAML dictionary as well for functions like _create()
        # set this BEL instance's relationships, signatures, term translations, etc.
        try:
            current_stored_dir = os.path.dirname(__file__)
            yaml_file_name = 'versions/bel_v{}.yaml'.format(self.version_dots_as_underscores)
            yaml_file_path = '{}/{}'.format(current_stored_dir, yaml_file_name)
            self.yaml_dict = yaml.load(open(yaml_file_path, 'r').read())

            self.translate_terms = func_name_translate(self)
            self.relationships = get_all_relationships(self)
            self.function_signatures = get_all_function_signatures(self)
            self.computed_sig_functions = get_all_computed_sig_functions(self)
        except Exception as e:
            print(e)
            print('Warning: The YAML file for version {} is not found.'.format(self.version))
            pass

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

        # check if user entered an empty string
        if statement == '':
            error = 'Please include a valid BEL statement.'
            return ParseObject(ast, error, err_visual)

        # pre-process to remove extra white space, add space after commas, etc.
        statement = preprocess_bel_line(statement)

        try:
            # see if an AST is returned without any parsing errors
            ast = self.parser.parse(statement, rule_name='start', semantics=self.semantics, trace=False)
        except FailedParse as e:
            # if an error is returned, send to handle_syntax, error
            error, err_visual = handle_syntax_error(e)
        except Exception as e:
            print(e)
            print(type(e))

        # return everything in a ParseObject
        return ParseObject(ast, error, err_visual)

    def stmt_components(self, statement: str):
        """
        Returns the components of a BEL statement as values within a dictionary under the keys 'subject',
        'relationship', and 'object'.

        Args:
            statement (str): BEL statement

        Returns:
            dict: The dictionary that contains the components as its values.
        """

        # create a dictionary with the keys defined
        components_dict = dict.fromkeys(['object', 'relationship', 'subject'])

        # send the statement to be parsed and grab the AST from the parse
        p = self.parse(statement)
        ast = p.ast

        if ast is None:  # if not AST is available, that must mean there was an error - print it
            components_dict['object'] = None
            components_dict['relationship'] = None
            components_dict['subject'] = None
            print(p.error)
            print(p.err_visual)
        else:  # else return the components in a dictionary
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

        components_dict = dict()
        components_dict['subject'] = ast.get('subject', None)

        # if a relationship exists, this means that an object must also exist
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
            list: A list of InvalidStatementObject objects.
        """

        # statements will be inside objects, so we need a new list for those
        list_of_bel_stmt_objs = []

        # if user specifies < 1 test statements, do as he/she wishes and return an empty list
        if count < 1:
            return list_of_bel_stmt_objs

        return create_invalid(self, count, max_params)

    def flatten(self, ast: AST):
        """
        Takes an AST and flattens it into a BEL statement string.

        Args:
            ast (AST): BEL AST

        Returns:
            str: The string generated from the AST.
        """

        # grab the three components of the AST
        s = ast.get('subject', None)
        r = ast.get('relationship', None)
        o = ast.get('object', None)

        # if no relationship, this means only subject is present
        if r is None:
            sub = decode(s)
            final = '{}'.format(sub)
        # else the full form BEL statement with subject, relationship, and object are present
        else:
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

        # create an empty list to put our loaded statements
        statements = []

        # open the file that we're loading statements off of
        f = open(filename)
        line_count = 0

        # for each statement in our file (each statement should be on a newline)
        for line in f:
            if line_count == loadn:  # once number of lines processed equals user specified, stop
                break

            if preprocess:  # if preprocess if selected, clean up the statement string
                line = preprocess_bel_line(line)
            else:
                line = line.strip()

            statements.append(line)
            line_count += 1

        # close the file and return the list
        f.close()

        return statements

    def validate(self, statement: str, strict: bool = False):
        """
        Validates a BEL statement and returns a ValidationObject. validate() simply calls parse() but will have a
        boolean to describe the existence of an AST from the ParseObject returned.

        Args:
            statement (str): BEL statement
            strict (bool): specify to use strict or loose parsing; defaults to loose

        Returns:
            ValidationObject: The ValidationObject which contain either an AST or error messages, and valid boolean.

        """

        # begins with a call to parse
        p = self.parse(statement)

        # checks for the existence of the AST tree from parse(), and sets the valid boolean accordingly.
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
            value_type (str): value type (function, modifier function, or relationship; makes sure we match right list)

        Returns:
            list: A list of suggested values.
        """

        # this function is in backlog!

        suggestions = []
        # # TODO: get the following list of things - initialize YAML into this library so we can grab all funcs,
        # # mfuncs, and r.
        # if value_type == 'function':
        #     suggestions = []
        #
        # elif value_type == 'mfunction':
        #     suggestions = []
        #
        # elif value_type == 'relationship':
        #     suggestions = []
        #
        # else:
        #     suggestions = []

        return suggestions

    def canonicalize(self, ast: AST):
        # TODO: this definition cannot be completed until TermStore API is complete.
        """
        Takes an AST and returns a canonicalized BEL statement string.

        Args:
            ast (AST): BEL AST

        Returns:
            str: The canonicalized string generated from the AST.
        """

    def computed(self, ast: AST):
        # TODO: this definition
        """
        Takes an AST and computes all canonicalized edges.

        Args:
            ast (AST): BEL AST

        Returns:
            list:  List of canonicalized computed edges to load into the EdgeStore.
        """

        # make empty list to hold our computed edge strings
        list_of_computed = []

        # get both subject and object (we don't need relationship because no computing happens for relationship)
        s = ast.get('subject', None)
        o = ast.get('object', None)

        # compute subject and add to list
        compute_list_subject = compute(s)
        list_of_computed.extend(compute_list_subject)

        if o is not None:  # if object exists, then compute object as well
            compute_list_object = compute(o)
            list_of_computed.extend(compute_list_object)

        return sorted(list(set(list_of_computed)))
