
from collections import defaultdict

from .elements import (ContainsClauseElement,
                    AlignmentClauseElement,
                    RightAlignedClauseElement, LeftAlignedClauseElement,
                    NotRightAlignedClauseElement, NotLeftAlignedClauseElement)

from .func import Count

from .helper import anchor_attributes, type_attributes

from .cypher import query_to_cypher, query_to_params

from polyglotdb.io.csv import save_results


class GraphQuery(object):
    """
    Base GraphQuery class.

    Extend this class to implement more advanced query functions.

    Parameters
    ----------
    corpus : :class:`polyglotdb.corpus.CorpusContext`
        The corpus to query
    to_find : str
        Name of the annotation type to search for
    """
    def __init__(self, corpus, to_find, is_timed):
        self.is_timed = is_timed
        self.corpus = corpus
        self.to_find = to_find
        self._criterion = []
        self._columns = [self.to_find.id.column_name('id'),
                        self.to_find.label.column_name('label')]
        self._additional_columns = []
        self._order_by = []
        self._group_by = []
        self._aggregate = []

        self._set_type_labels = []
        self._set_token_labels = []
        self._remove_type_labels = []
        self._remove_token_labels = []

        self._set_type = {}
        self._set_token = {}
        self._delete = False

    def clear_columns(self):
        """
        Remove any columns specified.  The default columns for any query
        are the id of the token and the label of the type.
        """
        self._columns = []
        return self

    @property
    def annotation_set(self):
        annotation_set = set()
        for c in self._criterion:
            annotation_set.update(c.annotations)
        return annotation_set

    def filter(self, *args):
        """
        Apply one or more filters to a query.
        """
        self._criterion.extend(args)
        return self

    def filter_contains(self, *args):
        """
        Deprecated, use ``filter`` instead.
        """
        self._criterion.extend(args)
        return self

    def filter_contained_by(self, *args):
        """
        Deprecated, use ``filter`` instead.
        """
        self._criterion.extend(args)
        return self

    def columns(self, *args):
        """
        Add one or more additional columns to the results.

        Columns should be :class:`polyglotdb.graph.attributes.Attribute` objects.
        """
        column_set = set(self._additional_columns)
        column_set.update(self._columns)
        args = [x for x in args if x not in column_set]
        self._additional_columns.extend(args)
        return self

    def filter_left_aligned(self, annotation_type):
        """
        Short cut function for aligning the queried annotations with
        another annotation type.

        Same as query.filter(g.word.begin == g.phone.begin).
        """
        self._criterion.append(LeftAlignedClauseElement(self.to_find, annotation_type))
        return self

    def filter_right_aligned(self, annotation_type):
        """
        Short cut function for aligning the queried annotations with
        another annotation type.

        Same as query.filter(g.word.end == g.phone.end).
        """
        self._criterion.append(RightAlignedClauseElement(self.to_find, annotation_type))
        return self

    def filter_not_left_aligned(self, annotation_type):
        """
        Short cut function for aligning the queried annotations with
        another annotation type.

        Same as query.filter(g.word.begin != g.phone.begin).
        """
        self._criterion.append(NotLeftAlignedClauseElement(self.to_find, annotation_type))
        return self

    def filter_not_right_aligned(self, annotation_type):
        """
        Short cut function for aligning the queried annotations with
        another annotation type.

        Same as query.filter(g.word.end != g.phone.end).
        """
        self._criterion.append(NotRightAlignedClauseElement(self.to_find, annotation_type))
        return self

    def cypher(self):
        """
        Generates a Cypher statement based on the query.
        """
        for c in self._criterion:
            try:
                if c.attribute.label == 'discourse':
                    for c2 in self._criterion:
                        c2.attribute.annotation.discourse_label = c.value
                    break
            except AttributeError:
                pass
        return query_to_cypher(self)

    def cypher_params(self):
        """
        Generates Cypher statement parameters based on the query.
        """
        return query_to_params(self)

    def group_by(self, *args):
        """
        Specify one or more fields for how aggregates should be grouped.
        """
        self._group_by.extend(args)
        return self

    def order_by(self, field, descending = False):
        """
        Specify how the results of the query should be ordered.

        Parameters
        ----------
        field : Attribute
            Determines what the ordering should be based on
        descending : bool, defaults to False
            Whether the order should be descending
        """
        self._order_by.append((field, descending))
        return self

    def discourses(self, output_name = None):
        """
        Add a column to the output for the name of the discourse that
        the annotations are in.

        Parameters
        ----------
        output_name : str, optional
            Name of the output column, defaults to "discourse"
        """
        if output_name is None:
            output_name = 'discourse'
        self = self.columns(self.to_find.discourse.column_name(output_name))
        return self

    def annotation_levels(self):
        """
        Returns a dictionary with annotation types as keys and positional
        annotation types as values.

        Used for constructing Cypher statements.
        """
        annotation_levels = defaultdict(set)
        for c in self._criterion:
            for a in c.annotations:
                key = getattr(self.corpus, a.type)
                key.discourse_label = a.discourse_label
                key = key.subset_type(*a.subset_type_labels)
                key = key.subset_token(*a.subset_token_labels)
                annotation_levels[key].add(a)
        for a in self._columns + self._group_by + self._additional_columns:
            t = a.base_annotation
            key = getattr(self.corpus, t.type)
            key = key.subset_type(*t.subset_type_labels)
            key = key.subset_token(*t.subset_token_labels)
            annotation_levels[key].add(t)

        return annotation_levels

    def times(self, begin_name = None, end_name = None):
        """
        Add columns for the beginnings and ends of the searched for annotations to
        the output.

        Parameters
        ----------
        begin_name : str, optional
            Specify the name of the column for beginnings, defaults to
            "begin"
        end_name : str, optional
            Specify the name of the column for ends, defaults to
            "end"
        """
        if begin_name is None:
            begin_name = 'begin'
        if end_name is None:
            end_name = 'end'
        self = self.columns(self.to_find.begin.column_name(begin_name))
        self = self.columns(self.to_find.end.column_name(end_name))
        return self

    def duration(self):
        """
        Add a column for the durations of the annotations to the output
        named "duration".
        """
        self._additional_columns.append(self.to_find.duration.column_name('duration'))
        return self

    def all(self):
        """
        Returns all results for the query
        """
        return self.corpus.graph.cypher.execute(self.cypher(), **self.cypher_params())

    def to_csv(self, path):
        """
        Same as ``all``, but the results of the query are output to the
        specified path as a CSV file.
        """
        save_results(self.corpus.graph.cypher.execute(self.cypher(), **self.cypher_params()), path)

    def count(self):
        """
        Returns the number of rows in the query.
        """
        self._aggregate = [Count()]
        cypher = self.cypher()
        value = self.corpus.graph.cypher.execute(cypher, **self.cypher_params())
        self._aggregate = []
        return value.one

    def aggregate(self, *args):
        """
        Aggregate the results of the query by a grouping factor or overall.
        Not specifying a ``group_by`` in the query will result in a single
        result for the aggregate from the whole query.
        """
        self._aggregate = args
        cypher = self.cypher()
        value = self.corpus.graph.cypher.execute(cypher, **self.cypher_params())
        if self._group_by:
            return value
        else:
            return value.one

    def set_type(self, *args, **kwargs):
        """
        Set properties of the returned types.
        """
        for k,v in kwargs.items():
            self._set_type[k] = v
        self._set_type_labels.extend(args)
        self.corpus.graph.cypher.execute(self.cypher(), **self.cypher_params())
        self._set_type = {}
        self._set_type_labels = []

    def set_token(self, *args, **kwargs):
        """
        Set properties of the returned tokens.
        """
        for k,v in kwargs.items():
            self._set_token[k] = v
        self._set_token_labels.extend(args)
        self.corpus.graph.cypher.execute(self.cypher(), **self.cypher_params())
        self._set_token = {}
        self._set_token_labels = []

    def delete(self):
        """
        Remove the results of a query from the graph.  CAUTION: this is
        irreversible.
        """
        self._delete = True
        self.corpus.graph.cypher.execute(self.cypher(), **self.cypher_params())
