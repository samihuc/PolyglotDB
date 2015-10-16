
from collections import defaultdict

from .elements import (ContainsClauseElement,
                    AlignmentClauseElement,
                    RightAlignedClauseElement, LeftAlignedClauseElement,
                    NotRightAlignedClauseElement, NotLeftAlignedClauseElement)

from .func import Count

from .cypher import query_to_cypher

from polyglotdb.io.csv import save_results

anchor_attributes = ['begin', 'end', 'duration', 'discourse']

class GraphQuery(object):
    def __init__(self, corpus, to_find, is_timed):
        self.is_timed = is_timed
        self.corpus = corpus
        self.to_find = to_find
        self._criterion = []
        self._contained_by_annotations = set()
        self._contains_annotations = set()
        self._columns = [self.to_find.id.column_name('id'),
                        self.to_find.label.column_name('label')]
        self._additional_columns = []
        self._order_by = []
        self._group_by = []
        self._aggregate = []

    def property_subqueries(self):
        queries = defaultdict(list)
        for c in self._criterion:
            if len(c.annotations) == 1:
                a = c.annotations[0]
                if a in self._contains_annotations:
                    continue
                if isinstance(c, AlignmentClauseElement):
                    continue
                if c.attribute.label == 'id':
                    continue
                if c.attribute.label not in anchor_attributes:
                    queries[a].append(c)
        return queries

    def anchor_subqueries(self):
        queries = defaultdict(list)
        for c in self._criterion:
            if len(c.annotations) == 1:
                a = c.annotations[0]
                if isinstance(c, AlignmentClauseElement):
                    queries[a].append(c)
                    continue
                if c.attribute.label in anchor_attributes:
                    queries[a].append(c)
        return queries

    @property
    def annotation_set(self):
        annotation_set = set()
        for c in self._criterion:
            annotation_set.update(c.annotations)
        return annotation_set

    def filter(self, *args):
        self._criterion.extend([x for x in args if x is not None])
        other_to_finds = [x for x in self.annotation_set if x.type != self.to_find.type]
        for o in other_to_finds:
            if o.pos == 0:
                if o.type in [x.type for x in self._contained_by_annotations]:
                    continue
                if o.type in [x.type for x in self._contains_annotations]:
                    continue
                self._contained_by_annotations.add(o) # FIXME
        return self

    def filter_contains(self, *args):
        args = [ContainsClauseElement(x.attribute, x.value) for x in args]
        self._criterion.extend(args)
        annotation_set = set(x.attribute.annotation for x in args)
        self._contains_annotations.update(annotation_set)
        return self

    def filter_contained_by(self, *args):
        self._criterion.extend(args)
        annotation_set = set(x.attribute.annotation for x in args)
        self._contained_by_annotations.update(annotation_set)
        return self

    def columns(self, *args):
        column_set = set(self._additional_columns)
        column_set.update(self._columns)
        args = [x for x in args if x not in column_set]
        self._additional_columns.extend(args)
        return self

    def filter_left_aligned(self, annotation_type):
        self._criterion.append(LeftAlignedClauseElement(self.to_find, annotation_type))
        return self

    def filter_right_aligned(self, annotation_type):
        self._criterion.append(RightAlignedClauseElement(self.to_find, annotation_type))
        return self

    def filter_not_left_aligned(self, annotation_type):
        self._criterion.append(NotLeftAlignedClauseElement(self.to_find, annotation_type))
        return self

    def filter_not_right_aligned(self, annotation_type):
        self._criterion.append(NotRightAlignedClauseElement(self.to_find, annotation_type))
        return self

    def cypher(self):
        return query_to_cypher(self)

    def group_by(self, field):
        self._group_by.append(field)
        return self

    def order_by(self, field, descending = False):
        self._order_by.append((field, descending))
        return self

    def times(self, begin_name = None, end_name = None):
        if begin_name is not None:
            self._additional_columns.append(self.to_find.begin.column_name('begin'))
        else:
            self._additional_columns.append(self.to_find.begin)
        if end_name is not None:
            self._additional_columns.append(self.to_find.end.column_name('end'))
        else:
            self._additional_columns.append(self.to_find.end)
        return self

    def duration(self):
        self._additional_columns.append(self.to_find.duration.column_name('duration'))
        return self

    def all(self):
        return self.corpus.graph.cypher.execute(self.cypher())

    def to_csv(self, path):
        save_results(self.corpus.graph.cypher.execute(self.cypher()), path)

    def count(self):
        self._aggregate = [Count()]
        cypher = self.cypher()
        value = self.corpus.graph.cypher.execute(cypher)
        return value.one

    def aggregate(self, *args):
        self._aggregate = args
        cypher = self.cypher()
        value = self.corpus.graph.cypher.execute(cypher)
        if self._group_by:
            return value
        else:
            return value.one
