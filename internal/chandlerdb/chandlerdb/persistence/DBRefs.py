#   Copyright (c) 2004-2008 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from weakref import ref

from chandlerdb.util.c import Nil, UUID, CLink, CLinkedMap, PersistentValue
from chandlerdb.item.c import ItemRef
from chandlerdb.persistence.c import Record
from chandlerdb.item.Children import Children
from chandlerdb.item.RefCollections import RefList
from chandlerdb.item.Indexes import NumericIndex
from chandlerdb.item.Indexed import Indexed
from chandlerdb.persistence.RepositoryError import MergeError


class PersistentRefs(PersistentValue):

    def __init__(self, view):

        super(PersistentRefs, self).__init__(view)

        self.store = view.store
        self._changedRefs = Nil
        
    def _iterrefs(self, firstKey, lastKey):

        version = self._owner().itsVersion
        nextKey = firstKey or self._firstKey
        view = self.itsView
        refIterator = None
        map = self._dict

        while nextKey != lastKey:
            key = nextKey
            link = map.get(key, None)
            if link is None:
                if refIterator is None:
                    if version == 0:
                        raise KeyError, key
                    refs = self.store._refs
                    refIterator = refs.refIterator(view, self.uuid, version)

                ref = refIterator.next(key)
                if ref is None:
                    refIterator.close()
                    raise KeyError, ('refIterator', key)
                pKey, nKey, alias, otherKey = ref[0:4]
                map[key] = link = CLink(self, ItemRef(key, view),
                                        pKey, nKey, alias, otherKey)
                if alias is not None:
                    aliases = self._aliases
                    if aliases is Nil:
                        self._aliases = {alias: key}
                    else:
                        aliases[alias] = key

            nextKey = link._nextKey
            yield key

        if lastKey is not None:
            yield lastKey

        if refIterator is not None:
            refIterator.close()

    def _iteraliases(self, firstKey, lastKey):

        version = self._owner().itsVersion
        nextKey = firstKey or self._firstKey
        view = self.itsView
        refIterator = None
        map = self._dict

        while nextKey is not None:
            key = nextKey
            link = map.get(key, None)
            if link is None:
                if refIterator is None:
                    if version == 0:
                        raise KeyError, key
                    refs = self.store._refs
                    refIterator = refs.refIterator(view, self.uuid, version)

                ref = refIterator.next(key)
                if ref is None:
                    refIterator.close()
                    raise KeyError, ('refIterator', key)
                pKey, nextKey, alias = ref
            else:
                nextKey = link._nextKey
                alias = link.alias

            if alias is not None:
                yield alias, key

            if key == lastKey:
                break

        if refIterator is not None:
            refIterator.close()

    def _iterChanges(self):

        uuid = self.uuid
        for key, (op, oldAlias) in self._changedRefs.iteritems():
            if key != uuid:
                if op == 0:
                    link = self._get(key)
                    assert oldAlias != link.alias
                    yield key, (op, link._previousKey, link._nextKey,
                                link.alias, oldAlias, link._otherKey)
                else:
                    yield key, (op, None, None, None, None, None)

    def _iterHistory(self, fromVersion, toVersion):

        uuid = self.uuid
        oldAliases = {}
        for (version, (collection, key),
             ref) in self.store._refs.iterHistory(self.itsView, uuid,
                                                  fromVersion, toVersion):
            if key != uuid:
                if ref is None:
                    yield key, (1, None, None, None, None, None)
                else:
                    alias = ref[2]
                    oldAlias = oldAliases.get(key, Nil)
                    if oldAlias != alias:
                        oldAliases[key] = alias
                    yield key, (0, ref[0], ref[1], alias, oldAlias, ref[3])

    def _setItem(self, item):

        if not self._flags & CLinkedMap.NEW:
            ref = self.store._refs.loadRef(self.itsView, self.uuid,
                                           self._owner().itsVersion, self.uuid,
                                           True)
            if ref is not None:
                self._firstKey, self._lastKey, self._count = ref[0:3]

    def _changeRef(self, key, link, oldAlias=Nil):

        if key is not None and not self.itsView.isLoading():
            changedRefs = self._changedRefs
            if changedRefs is Nil:
                self._changedRefs = {key: (0, oldAlias)}
            else:
                op, alias = changedRefs.get(key, (1, Nil))
                if op != 0:
                    if oldAlias is not Nil:
                        if alias is Nil:
                            alias = oldAlias
                        elif alias == oldAlias:
                            alias = Nil
                    changedRefs[key] = (0, alias)

    def _removeRef_(self, key, link):

        if not self.itsView.isLoading():
            changedRefs = self._changedRefs
            if changedRefs is Nil:
                self._changedRefs = {key: (1, link.alias or Nil)}
            else:
                op, alias = changedRefs.get(key, (-1, Nil))
                if op == -1:
                    if not self._flags & CLinkedMap.NEW:
                        if link.alias is None:
                            alias = Nil
                        else:
                            alias = link.alias
                        changedRefs[key] = (1, alias)
                elif op == 0:
                    if self._flags & CLinkedMap.NEW:
                        del changedRefs[key]
                    else:
                        if alias is Nil and link.alias is not None:
                            alias = link.alias
                        changedRefs[key] = (1, alias)
            return link
        else:
            raise ValueError, ('_removeRef_ during load', self.uuid,
                               self._owner, self._name, self._otherName, key)

    def _isRemoved(self, key):

        change = self._changedRefs.get(key, None)
        if change is not None:
            return change[0] == 1

        return False

    def _loadRef(self, key):

        if self._isRemoved(key):
            return None
        
        return self.store._refs.loadRef(self.itsView, self.uuid,
                                        self._owner().itsVersion, key)

    def _deleteRef(self, key, version):

        return self.store._refs.deleteRef(self.uuid, version, key)

    def resolveAlias(self, alias, load=True):

        key = None
        if load:
            view = self.itsView
            key = self.store._names.readName(view, view.itsVersion,
                                             self.uuid, alias)
            if key is not None:
                op, oldAlias = self._changedRefs.get(key, (0, Nil))
                if oldAlias == alias:
                    key = None

        return key

    def _clearDirties(self):

        self._changedRefs = Nil

    def _applyChanges(self, changes, history, ask):

        view = self.itsView
        moves = {}
        done = set()

        def place(k, pK):
            self.place(k, pK)
            nK = changes[k][2]
            while nK in done and self.place(nK, k):
                k = nK
                nK = changes[k][2]

        try:
            # allow deleted refs to return for merging
            self._flags |= CLinkedMap.MERGING

            for key, (op, prevKey, nextKey,
                      alias, oldAlias, otherKey) in changes.iteritems():
                if key in history:
                    merge = True
                    hOp, hPrevKey, hNextKey, hAlias, hOldAlias, hOtherKey = history[key]
                else:
                    merge = False

                if op == 1:
                    #if key in history:
                    #    view._e_2_move(self, key)
                    if key in self:
                        self._removeRef(key)
                else:
                    if alias is not None:
                        resolvedKey = self.resolveAlias(alias)
                        while resolvedKey not in (None, key):
                            if ask is not None:
                                newAlias = ask(MergeError.ALIAS, self._name,
                                               (key, resolvedKey, alias))
                            else:
                                newAlias = alias
                            if newAlias == alias:
                                view._e_2_name(self, resolvedKey, key, alias)
                            else:
                                alias = newAlias
                                resolvedKey = self.resolveAlias(alias)

                    if key in self:
                        link = self._get(key)
                        if oldAlias is not Nil:
                            if link.alias != alias:
                                if merge and hOldAlias not in (Nil, hAlias):
                                    view._e_1_name(self, key, alias, hAlias)
                                self.setAlias(key, alias)
                    elif merge is True and hOp == 1:
                        # conflict: the ref was removed, resolve 
                        #           in favor of history
                        continue
                    else:
                        self._setRef(ItemRef(key, view), alias, None, otherKey)
                        link = self._get(key)

                    if link._previousKey != prevKey:
                        if prevKey is None or prevKey in self:
                            place(key, prevKey)
                        else:
                            moves[prevKey] = key

                    done.add(key)

        finally:
            self._flags &= ~CLinkedMap.MERGING

        for prevKey, key in moves.iteritems():
            if prevKey in self:
                place(key, prevKey)
                

class DBRefList(RefList, PersistentRefs):

    def __init__(self, view, item, name, otherName, dictKey,
                 readOnly, new, uuid):

        self.uuid = uuid or UUID()

        PersistentRefs.__init__(self, view)
        RefList.__init__(self, view, item, name, otherName, dictKey, readOnly,
                         (CLinkedMap.NEW if new else 0) | CLinkedMap.LOAD)

    def iterkeys(self, excludeIndexes=False, firstKey=None, lastKey=None):

        return self._iterrefs(firstKey, lastKey)

    def iteraliases(self, firstKey=None, lastKey=None):

        return self._iteraliases(firstKey, lastKey)

    def resolveAlias(self, alias, load=True):

        key = RefList.resolveAlias(self, alias, load)
        if key is None and load and not self._flags & CLinkedMap.NEW:
            key = PersistentRefs.resolveAlias(self, alias, load)

        return key
            
    def linkChanged(self, link, key, oldAlias=Nil):

        self._changeRef(key, link, oldAlias)
        
    def _removeRef_(self, other):

        link = RefList._removeRef_(self, other)
        if link is not None:
            link = PersistentRefs._removeRef_(self, other.itsUUID, link)

        return link

    def _setOwner(self, item, name):

        RefList._setOwner(self, item, name)
        PersistentRefs._setItem(self, item)

    def _saveValues(self, version):

        store = self.store
        refs = store._refs
        names = store._names
        uuid = self.uuid
        item = self._owner()
        aliases = self._aliases

        if __debug__:
            if not (self._flags & CLinkedMap.NEW or
                    item.isAttributeDirty(self._name, item._references) or
                    len(self._changedRefs) == 0):
                raise AssertionError, '%s.%s not marked dirty' %(item._repr_(),
                                                                 self._name)

        size = refs.put_record(Record(Record.UUID, uuid,
                                      Record.UUID, uuid,
                                      Record.INT, ~version),
                               Record(Record.UUID_OR_NONE, self._firstKey,
                                      Record.UUID_OR_NONE, self._lastKey,
                                      Record.INT, self._count,
                                      Record.UUID_OR_KEYWORD, None))
        nilNone = (Nil, None)
            
        for key, (op, oldAlias) in self._changedRefs.iteritems():
            if op == 0:               # change
                link = self._get(key, False)

                previous = link._previousKey
                next = link._nextKey
                alias = link.alias
                otherKey = link._otherKey

                size += refs.put_record(Record(Record.UUID, uuid,
                                               Record.UUID, key,
                                               Record.INT, ~version),
                                        Record(Record.UUID_OR_NONE, previous,
                                               Record.UUID_OR_NONE, next,
                                               Record.KEYWORD, alias,
                                               Record.UUID_OR_KEYWORD, otherKey))
                if (oldAlias not in nilNone and
                    oldAlias != alias and
                    oldAlias not in aliases):
                    size += names.writeName(version, uuid, oldAlias, None)
                if alias is not None:
                    size += names.writeName(version, uuid, alias, key)
                        
            elif op == 1:             # remove
                size += self._deleteRef(key, version)
                if oldAlias not in nilNone and oldAlias not in aliases:
                    size += names.writeName(version, uuid, oldAlias, None)

            else:                     # error
                raise ValueError, op

        return size
        
    def _clearDirties(self):

        self._flags &= ~CLinkedMap.NEW

        PersistentRefs._clearDirties(self)
        Indexed._clearDirties(self)

    def _isDirty(self):

        return len(self._changedRefs) > 0


class DBStandAloneRefList(DBRefList):

    def __init__(self, view, uuid, version):

        super(DBStandAloneRefList, self).__init__(view, None, None, None, None,
                                                  True, False, uuid)
        self.itsVersion = version
        self._setOwner(self, None)

    def __repr__(self):

        return '<%s: %s(%d)>' %(type(self).__name__, self.uuid, self.itsVersion)

    def __iter__(self):

        view = self.itsView
        for key in self.iterkeys():
            yield view.find(key)

    def itervalues(self):

        return iter(self)

    def _setOwner(self, owner, name):

        if owner is None:
            self._owner = Nil
        else:
            self._owner = ref(owner)

        PersistentRefs._setItem(self, owner)

    def _isDirty(self):

        return False


class DBNumericIndex(NumericIndex):

    def __init__(self, view, **kwds):

        super(DBNumericIndex, self).__init__(**kwds)

        self.view = view
        self._changedKeys = {}

        if not kwds.get('loading', False):

            if 'uuid' in kwds:
                self._uuid = UUID(kwds['uuid'])
                self._headKey = UUID(kwds['head'])
                self._tailKey = UUID(kwds['tail'])
            else:
                self._uuid = UUID()
                self._headKey = UUID()
                self._tailKey = UUID()

            self.__init()

    def __init(self):
    
        self._version = 0

    def _keyChanged(self, key):

        self._changedKeys[key] = self[key]

    def _iterChanges(self):

        uuids = (self._uuid, self._headKey, self._tailKey)
        for key, node in self._changedKeys.iteritems():
            if key not in uuids:
                if node is None:
                    yield key, None
                else:
                    yield key, key

    def removeKey(self, key):

        removed, selected = super(DBNumericIndex, self).removeKey(key)
        if removed:
            self._changedKeys[key] = None

        return removed, selected

    def isPersistent(self):

        return True

    def _restore(self, version):

        indexes = self.view.store._indexes.c
        
        view = self.view
        self._version = version
        head = indexes.loadKey(view, self._uuid, version, self._headKey)
        tail = indexes.loadKey(view, self._uuid, version, self._tailKey)

        if head is not None:
            self.skipList._head = head
        if tail is not None:
            self.skipList._tail = tail

    def _loadKey(self, key):

        node = None
        version = self._version

        if version > 0:
            if self._changedKeys.get(key, Nil) is None:   # removed key
                return None

            view = self.view
            node = view.store._indexes.c.loadKey(view, self._uuid, version, key)
            if node is not None:
                self[key] = node

        return node

    def iterkeys(self, firstKey=None, lastKey=None):

        version = self._version
        view = self.view

        nextKey = firstKey or self.getFirstKey()
        descending = self._descending
        sup = super(DBNumericIndex, self)
        nodeIterator = None

        while nextKey != lastKey:
            key = nextKey
            node = sup.get(key, None)
            if node is None:
                if nodeIterator is None:
                    if version == 0:
                        raise KeyError, key
                    indexes = view.store._indexes
                    nodeIterator = indexes.nodeIterator(view, self._uuid,
                                                        version)
                node = nodeIterator.next(key)
                self[key] = node

            if descending:
                nextKey = node[1].prevKey
            else:
                nextKey = node[1].nextKey
            yield key

        if lastKey is not None:
            yield lastKey

    def _writeValue(self, itemWriter, record, version):

        super(DBNumericIndex, self)._writeValue(itemWriter, record, version)

        itemWriter.indexes.append(self._uuid)
        record += (Record.INT, self._count,
                   Record.UUID, self._uuid,
                   Record.UUID, self._headKey,
                   Record.UUID, self._tailKey)

    def _readValue(self, itemReader, offset, data):

        offset = super(DBNumericIndex, self)._readValue(itemReader,
                                                        offset, data)
        (self._count, self._uuid,
         self._headKey, self._tailKey) = data[offset:offset+4]

        self.__init()

        return offset + 4

    def _saveValues(self, version):

        indexes = self.view.store._indexes

        size = indexes.saveKey(self._uuid, version, self._headKey,
                               self.skipList._head)
        size += indexes.saveKey(self._uuid, version, self._tailKey,
                                self.skipList._tail)
        for key, node in self._changedKeys.iteritems():
            size += indexes.saveKey(self._uuid, version, key, node)

        self._version = version

        return size

    def _clearDirties(self):

        self._changedKeys.clear()
        

class DBChildren(Children, PersistentRefs):

    def __init__(self, view, item, new=True):

        self.uuid = item.itsUUID

        PersistentRefs.__init__(self, view)
        Children.__init__(self, view, item,
                          (CLinkedMap.NEW if new else 0) | CLinkedMap.LOAD)

    def iterkeys(self, firstKey=None, lastKey=None):

        return self._iterrefs(firstKey, lastKey)

    def _setItem(self, item):

        Children._setItem(self, item)
        PersistentRefs._setItem(self, item)

    def _load(self, key):

        if self._flags & CLinkedMap.NEW:
            return False

        if not self._isRemoved(key):
            child = self.itsView.find(key)
            if child is not None or self._flags & CLinkedMap.MERGING:
                if key not in self._dict:
                    try:
                        loading = self.itsView._setLoading(True)
                        if not self._loadChild(key, child):
                            return False
                    finally:
                        self.itsView._setLoading(loading, True)
                return True

        return False

    def _loadChild(self, key, child):

        if key not in self._dict:
            ref = self._loadRef(key)
            if ref is None:  # during merge it may not be there
                return False
            prevKey, nextKey, alias, otherKey = ref[0:4]
            self._dict[key] = CLink(self, child.itsRef, prevKey, nextKey,
                                    alias, otherKey)
            if alias is not None:
                aliases = self._aliases
                if aliases is Nil:
                    self._aliases = {alias: key}
                else:
                    aliases[alias] = key
        else:
            self._dict[key].value = child.itsRef

        return True

    def resolveAlias(self, alias, load=True):

        key = Children.resolveAlias(self, alias, load)
        if key is None and not self._flags & CLinkedMap.NEW:
            key = PersistentRefs.resolveAlias(self, alias, load)

        return key
            
    def linkChanged(self, link, key, oldAlias=Nil):

        super(DBChildren, self).linkChanged(link, key, oldAlias)
        self._changeRef(key, link, oldAlias)

    def __delitem__(self, key):

        self._removeRef_(key)

    def _removeRef(self, key):
        
        self._removeRef_(key)

    def _removeRef_(self, key):
        
        link = super(DBChildren, self).__delitem__(key)
        link = PersistentRefs._removeRef_(self, key, link)

        return link

    def _setRef(self, other, alias=None, dictKey=None, otherKey=None):

        link = CLink(self, other.itsRef, None, None, alias, otherKey)
        self[other.itsUUID] = link

    def _append(self, child):

        loading = self.itsView.isLoading()
        if loading:
            self._loadChild(child.itsUUID, child)
        else:
            key = child.itsUUID
            link = self._get(key, True, True)
            if link is None:
                self[key] = CLink(self, child.itsRef, None, None,
                                  child.itsName, None)
            else:
                link.value = child.itsRef
                if link.alias != child.itsName:
                    self.setAlias(key, child.itsName)

    def _saveValues(self, version):

        store = self.store
        refs = store._refs
        names = store._names
        uuid = self.uuid
        unloads = []
        
        size = refs.put_record(Record(Record.UUID, uuid,
                                      Record.UUID, uuid,
                                      Record.INT, ~version),
                               Record(Record.UUID_OR_NONE, self._firstKey,
                                      Record.UUID_OR_NONE, self._lastKey,
                                      Record.INT, self._count,
                                      Record.UUID_OR_KEYWORD, None))
                
        nilNone = (Nil, None)
        for key, (op, oldAlias) in self._changedRefs.iteritems():
    
            if op == 0:               # change
                link = self._get(key, False)
                previous = link._previousKey
                next = link._nextKey
                alias = link.alias
                otherKey = link._otherKey

                size += refs.put_record(Record(Record.UUID, uuid,
                                               Record.UUID, key,
                                               Record.INT, ~version),
                                        Record(Record.UUID_OR_NONE, previous,
                                               Record.UUID_OR_NONE, next,
                                               Record.KEYWORD, alias,
                                               Record.UUID_OR_KEYWORD, otherKey))

                if (oldAlias not in nilNone and
                    oldAlias != alias and
                    oldAlias not in self._aliases):
                    size += names.writeName(version, self.uuid, oldAlias, None)
                if alias is not None:
                    size += names.writeName(version, self.uuid, alias, key)

                if link.value is None:
                    unloads.append((key, link.alias))

            elif op == 1:             # remove
                size += self._deleteRef(key, version)
                if oldAlias not in nilNone and oldAlias not in self._aliases:
                    size += names.writeName(version, self.uuid, oldAlias, None)

            else:                     # error
                raise ValueError, op

        for key, alias in unloads:
            self._remove(key)
            if alias is not None:
                del self._aliases[alias]

        return size

    def _clearDirties(self):

        self._flags &= ~CLinkedMap.NEW
        PersistentRefs._clearDirties(self)
