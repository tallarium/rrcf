import numpy as np

class RCTree:
    """
    Robust random cut tree data structure.

    Example usage:
    X = np.random.randn(100,2)
    tree = RCTree(X)

    Attributes:
    -----------
    root: Pointer to root of tree
    leaves: Dict containing pointers to all leaves in tree
    """
    def __init__(self, X, root=None):
        # Initialize dict for leaves
        self.leaves = {}
        # Initialize tree root
        self.root = root
        # Store dimension of dataset
        self.ndim = X.shape[1]
        # Set node above to None in case of bottom-up search
        self.u = None
        # Store bbox of points
        self._bbox = np.column_stack([X.min(axis=0), X.max(axis=0)])
        # Create RRC Tree
        S = np.ones(X.shape[0], dtype=np.bool)
        self._mktree(X, S, parent=self)
        # Remove parent of root
        self.root.u = None
        # Count all leaves under each branch
        self._count_all_top_down(self.root)

    def _cut(self, X, S, parent=None, side='l'):
        # Find max and min over all d dimensions
        xmax = X[S].max(axis=0)
        xmin = X[S].min(axis=0)
        # Compute l
        l = xmax - xmin
        l /= l.sum()
        # Determine dimension to cut
        q = np.random.choice(self.ndim, p=l)
        # Determine value for split
        p = np.random.uniform(xmin[q], xmax[q])
        # Determine subset of points to left
        S1 = (X[:,q] <= p) & (S)
        # Determine subset of points to right
        S2 = (~S1) & (S)
        # Create new child node
        child = Branch(q=q, p=p, u=parent)
        # Link child node to parent
        if parent is not None:
            setattr(parent, side, child)
        return S1, S2, child

    def _mktree(self, X, S, parent=None, side='root', depth=0):
        # Increment depth as we traverse down
        depth += 1
        # Create a cut according to definition 1
        S1, S2, branch = self._cut(X, S, parent=parent, side=side)
        # If S1 does not contain an isolated point...
        if S1.sum() > 1:
            # Recursively construct tree on S1
            self._mktree(X, S1, parent=branch, side='l', depth=depth)
        # Otherwise...
        else:
            # Create a leaf node from isolated point
            i = np.asscalar(np.flatnonzero(S1))
            leaf = Leaf(i=i, d=depth, u=branch)
            # Link leaf node to parent
            branch.l = leaf
            self.leaves[i] = leaf
        # If S2 does not contain an isolated point...
        if S2.sum() > 1:
            # Recursively construct tree on S2
            self._mktree(X, S2, parent=branch, side='r', depth=depth)
        # Otherwise...
        else:
            # Create a leaf node from isolated point
            i = np.asscalar(np.flatnonzero(S2))
            leaf = Leaf(i=i, d=depth, u=branch)
            # Link leaf node to parent
            branch.r = leaf
            self.leaves[i] = leaf
        # Decrement depth as we traverse back up
        depth -= 1

    def delete_leaf(self, x):
        # Pop pointer to leaf out of leaves dict
        node = self.leaves.pop(x)
        # Find parent and grandparent
        parent = node.u
        grandparent = parent.u
        # Find sibling
        if node is parent.l:
            sibling = parent.r
        else:
            sibling = parent.l
        # Set parent of sibling to grandparent
        sibling.u = grandparent
        # Short-circuit grandparent to sibling
        if parent is grandparent.l:
            grandparent.l = sibling
        else:
            grandparent.r = sibling
        # Update depths
        self.traverse(grandparent, op=self._increment_depth, inc=-1)
        # Collect garbage
        del node
        del parent

    def traverse(self, node, op=(lambda x: None), *args, **kwargs):
        '''
        Traverse tree recursively, calling operation given by op on leaves

        node: node in RCTree
        op: function to call on each leaf
        *args: positional arguments to op
        **kwargs: keyword arguments to op
        '''
        if isinstance(node, Branch):
            if node.l:
                self.traverse(node.l, op=op, *args, **kwargs)
            if node.r:
                self.traverse(node.r, op=op, *args, **kwargs)
        else:
            op(node, *args, **kwargs)

    def _count_all_top_down(self, node):
        '''
        Traverse tree recursively, calling operation given by op on leaves

        node: node in RCTree
        op: function to call on each branch
        *args: positional arguments to op
        **kwargs: keyword arguments to op
        '''
        if isinstance(node, Branch):
            if node.l:
                self._count_all_top_down(node.l)
            if node.r:
                self._count_all_top_down(node.r)
            node.n = node.l.n + node.r.n

    def query(self, point, node=None):
        '''
        Search for leaf nearest to point

        point: point to search for
        node: node in RCTree
        '''
        if node is None:
            node = self.root
        return self._query(point, node)

    def _count_leaves(self, node):
        num_leaves = np.array(0, dtype=np.int64)
        self.traverse(node, op=self._accumulate, accumulator=num_leaves)
        num_leaves = np.asscalar(num_leaves)
        return num_leaves

    def disp(self, x):
        '''
        Compute displacement at leaf x

        x: index of point
        '''
        # Get node and parent
        node = self.leaves[x]
        parent = node.u
        # Find sibling
        if node is parent.l:
            sibling = parent.r
        else:
            sibling = parent.l
        # Count number of nodes in sibling subtree
        displacement = np.array(0, dtype=np.int64)
        self.traverse(sibling, op=self._accumulate, accumulator=displacement)
        displacement = np.asscalar(displacement)
        return displacement

    def codisp(self, x):
        '''
        Compute collusive displacement at leaf x

        x: index of point
        '''
        node = self.leaves[x]
        results = []
        displacement = np.array(0, dtype=np.int64)
        num_deleted  = np.array(0, dtype=np.int64)
        for _ in range(node.d):
            parent = node.u
            if parent is None:
                break
            if node is parent.l:
                sibling = parent.r
            else:
                sibling = parent.l
            self.traverse(node, op=self._accumulate, accumulator=num_deleted)
            self.traverse(sibling, op=self._accumulate, accumulator=displacement)
            result = np.asscalar(displacement / num_deleted)
            results.append(result)
            node = parent
        return max(results)

    def disp_all(self):
        '''
        Compute displacement at every leaf
        '''
        # Get node and parent
        results = {}
        for index, leaf in self.leaves.items():
            node = leaf
            parent = node.u
            # Find sibling
            if node is parent.l:
                sibling = parent.r
            else:
                sibling = parent.l
            # Count number of nodes in sibling subtree
            results[index] = sibling.n
        return results

    def codisp_all(self):
        '''
        Compute collusive displacement at every leaf

        x: index of point
        '''
        results = {}
        for index, leaf in self.leaves.items():
            node = leaf
            leaf_results = []
            for _ in range(node.d):
                parent = node.u
                if parent is None:
                    break
                if node is parent.l:
                    sibling = parent.r
                else:
                    sibling = parent.l
                num_deleted = node.n
                displacement = sibling.n
                result = (displacement / num_deleted)
                leaf_results.append(result)
                node = parent
            results[index] = max(leaf_results)
        return results

    def _query(self, point, node):
        if isinstance(node, Leaf):
            return node
        else:
            if point[node.q] <= node.p:
                return self._query(point, node.l)
            else:
                return self._query(point, node.r)

    def _increment_depth(self, x, inc=1):
        x.d += (inc)

    def _accumulate(self, x, accumulator):
        accumulator += 1

    def _get_leaves(self, x, stack):
        stack.append(x.i)

class Branch:
    __slots__ = ['q', 'p', 'l', 'r', 'u', 'n']
    def __init__(self, q, p, l=None, r=None, u=None, n=0):
        self.l = l
        self.r = r
        self.u = u
        self.q = q
        self.p = p
        self.n = n

class Leaf:
    __slots__ = ['i', 'd', 'u', 'n']
    def __init__(self, i, d=None, u=None, n=1):
        self.u = u
        self.i = i
        self.d = d
        self.n = n

