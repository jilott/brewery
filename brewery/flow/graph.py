from collections import OrderedDict
from brewery.common import get_logger
import collections

Connection = collections.namedtuple("Connection",
                                    ["source", "target",
                                     "source_outlet", "target_outlet"])


class Graph(object):
    """Data processing stream"""
    def __init__(self, nodes=None, connections=None):
        """Creates a node graph with connections.

        :Parameters:
            * `nodes` - dictionary with keys as node names and values as nodes
            * `connections` - list of two-item tuples. Each tuple contains source and target node
              or source and target node name.
        """

        super(Graph, self).__init__()
        connections = connections or []
        self.nodes = OrderedDict()
        self.connections = set()

        self.logger = get_logger()

        self._name_sequence = 1

        if nodes:
            try:
                for name, node in nodes.items():
                    self.add(node, name)
            except:
                raise ValueError("Nodes should be a dictionary, is %s" % type(nodes))

        for connection in connections:
            self.connect(*connection)

    def _generate_node_name(self):
        """Generates unique name for a node"""
        while 1:
            name = "node" + str(self._name_sequence)
            if name not in self.nodes.keys():
                break
            self._name_sequence += 1

        return name

    def add(self, node, name=None):
        """Add a `node` into the stream. Does not allow to add named node if
        node with given name already exists. Generate node name if not
        provided. Node name is generated as ``node`` + sequence number.
        Uniqueness is tested."""

        name = name or self._generate_node_name()

        if name in self.nodes:
            raise KeyError("Node with name %s already exists" % name)

        if node in self.nodes.values():
            raise ValueError("Node %s already exists" % node)

        self.nodes[name] = node

        return name

    def node_name(self, node):
        """Returns name of `node`."""
        # There should not be more
        if not node:
            raise ValueError("No node provided")

        names = [key for key,value in self.nodes.items() if value==node]

        if len(names) == 1:
            return names[0]
        elif len(names) > 1:
            raise StreamError("There are more references to the same node")
        else: # if len(names) == 0
            raise StreamError("Can not find node '%s'" % node)

    def rename_node(self, node, name):
        """Sets a name for `node`. Raises an exception if the `node` is not
        part of the stream, if `name` is empty or there is already node with
        the same name. """

        if not name:
            raise ValueError("No node name provided for rename")
        if name in self.nodes():
            raise ValueError("Node with name '%s' already exists" % name)

        old_name = self.node_name(node)

        del self.nodes[old_name]
        self.nodes[name] = node

    def node(self, reference):
        """Coalesce node reference: `reference` should be either a node name
        or a node. Returns the node object."""

        try:
            return self.nodes[reference]
        except KeyError:
            if reference in self.nodes.values():
                return reference
            else:
                raise ValueError("Unable to find node '%s'" % reference)

    def remove(self, node):
        """Remove a `node` from the stream. Also all connections will be
        removed."""

        # Allow node name, get the real node object
        if isinstance(node, basestring):
            name = node
            node = self.nodes[name]
        else:
            name = self.node_name(node)

        del self.nodes[name]

        remove = [c for c in self.connections if c.source == node or c.target == node]

        for connection in remove:
            self.connections.remove(connection)

    def connect(self, source, target, source_outlet=None, target_outlet=None):
        """Connects source node and target node. Nodes can be provided as
        objects or names."""
        connection = Connection(self.node(source),
                                self.node(target),
                                source_outlet,
                                target_outlet)
        self.connections.add(connection)

    def remove_connection(self, source, target, source_outlet=None,
                          target_outlet=None, all_=False):
        """Remove connection with `name` between source and target nodes, if exists.
        if `all_` is true, then all connections between the two nodes are
        removed"""

        if all_:
            for conn in self.connections:
                if conn.source == source and conn.target == target:
                    self.connections.discard(conn)
        else:
            connection = (self.node(source), self.node(target),
                            source_outlet, target_outlet)
            self.connections.discard(connection)

    def sorted_nodes(self, nodes=None):
        """
        Return topologically sorted nodes. If `nodes` is not provided,
        then all nodes are used.

        Algorithm::

            L = Empty list that will contain the sorted elements
            S = Set of all nodes with no incoming edges
            while S is non-empty do
                remove a node n from S
                insert n into L
                for each node m with an edge e from n to m do
                    remove edge e from the graph
                    if m has no other incoming edges then
                        insert m into S
            if graph has edges then
                raise exception: graph has at least one cycle
            else
                return proposed topologically sorted order: L
        """
        # FIXME: check that the nodes specified as argument are in the
        # receiver

        def is_source(node, connections):
            for connection in connections:
                if node == connection.target:
                    return False
            return True

        def source_connections(node, connections):
            conns = set()
            for connection in connections:
                if node == connection.source:
                    conns.add(connection)
            return conns

        if not nodes:
            nodes = set(self.nodes.values())

        connections = self.connections.copy()
        sorted_nodes = []

        # Find source nodes:
        source_nodes = set([n for n in nodes if is_source(n, connections)])

        # while S is non-empty do
        while source_nodes:
            # remove a node n from S
            node = source_nodes.pop()
            # insert n into L
            sorted_nodes.append(node)

            # for each node m with an edge e from n to m do
            s_connections = source_connections(node, connections)
            for connection in s_connections:
                #     remove edge e from the graph
                m = connection.target
                connections.remove(connection)
                #     if m has no other incoming edges then
                #         insert m into S
                if is_source(m, connections):
                    source_nodes.add(m)

        # if graph has edges then
        #     output error message (graph has at least one cycle)
        # else
        #     output message (proposed topologically sorted order: L)

        if connections:
            raise Exception("Steram has at least one cycle (%d connections left of %d)" % (len(connections), len(self.connections)))

        return sorted_nodes

    def node_targets(self, node):
        """Return nodes that `node` passes data into."""
        node = self.node(node)
        nodes =[conn.target for conn in self.connections if conn.source == node]
        return nodes

    def node_sources(self, node):
        """Return nodes that provide data for `node`."""
        node = self.node(node)
        nodes =[conn.source for conn in self.connections if conn.target == node]
        return nodes

    def connections_with_source(self, node):
        """Returns connectios that have `node` as source."""
        node = self.node(node)
        connections =[conn for conn in self.connections if conn.source == node]
        return connections

    def connections_with_target(self, node):
        """Returns connectios that have `node` as target."""
        node = self.node(node)
        connections =[c for c in self.connections if c.target == node]
        return connections
