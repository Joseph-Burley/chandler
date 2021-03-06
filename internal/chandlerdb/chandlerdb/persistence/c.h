/*
 *  Copyright (c) 2003-2008 Open Source Applications Foundation
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */


#include <db.h>

#include "../item/item.h"
#include "../util/uuid.h"
#include "../util/skiplist.h"
#include "../schema/attribute.h"
#include "record.h"
#include "view.h"

#define LOAD_TYPE(m, name) \
    name = (PyTypeObject *) PyObject_GetAttrString(m, #name);

#define LOAD_OBJ(m, name) \
    name = PyObject_GetAttrString(m, #name);

#define LOAD_FN(m, name) \
    { PyObject *cobj = PyObject_GetAttrString(m, #name); \
      name = (name##_fn) PyCObject_AsVoidPtr(cobj); \
      Py_DECREF(cobj); }

#define LOAD_EXC(m, name) \
    PyExc_##name = PyObject_GetAttrString(m, #name)

#define MAKE_EXC(m, name, base)                                          \
    PyExc_##name = PyErr_NewException("chandlerdb.persistence.c." #name, \
                                      PyExc_##base, NULL);               \
    PyObject_SetAttrString(m, #name, PyExc_##name)


#define SET_DB_INT(dict, name) PyDict_SetItemString_Int(dict, #name, name)

/* db error codes are documented to be in the -30,800 to -30,999 range */
#define DB_PYTHON_ERROR -30801

typedef struct {
    PyObject_HEAD
    unsigned int status;
    PyObject *store;
} t_repository;

typedef struct {
    PyObject_HEAD
    DB *db;
    PyObject *associate_cb;
} t_db;

typedef struct {
    PyObject_HEAD
    DBC *dbc;
} t_cursor;

typedef struct {
    PyObject_HEAD
    DB_ENV *db_env;
    PyObject *errfile;
} t_env;

typedef struct {
    PyObject_HEAD
    DB_TXN *txn;
} t_txn;

typedef struct {
    PyObject_HEAD
    DB_LOCK lock;
    t_env *env;
    int held;
} t_lock;

typedef struct {
    PyObject_HEAD
    PyObject *txn;
    int status;
    int count;
    int mvcc;
} t_transaction;

typedef struct {
    PyObject_HEAD
    PyObject *repository;
    PyObject *key;
} t_store;

enum {
    TXN_STARTED = 0x0001,
    TXN_NESTED  = 0x0002,
};

extern PyTypeObject *CView;
extern PyTypeObject *CRepository;
extern PyTypeObject *CStore;
extern PyTypeObject *CItem;
extern PyTypeObject *ItemRef;
extern PyTypeObject *CDB;
extern PyTypeObject *CDBCursor;
extern PyTypeObject *CDBEnv;
extern PyTypeObject *CDBTxn;
extern PyTypeObject *CDBLock;
extern PyTypeObject *Record;
extern PyTypeObject *CtxMgr;
extern PyTypeObject *SkipList;
extern PyTypeObject *SkipList_Node;

extern PyUUID_Check_fn PyUUID_Check;
extern PyUUID_Make16_fn PyUUID_Make16;
extern _hash_bytes_fn _hash_bytes;
extern CAttribute_invokeAfterChange_fn CAttribute_invokeAfterChange;
extern CItem_getLocalAttributeValue_fn CItem_getLocalAttributeValue;

extern PyObject *PyExc_DBError;
extern PyObject *PyExc_DBLockDeadlockError;
extern PyObject *PyExc_DBLockNotGrantedError;
extern PyObject *PyExc_DBAccessError;
extern PyObject *PyExc_DBBusyError;
extern PyObject *PyExc_DBInvalidArgError;
extern PyObject *PyExc_DBNoSpaceError;
extern PyObject *PyExc_DBNotFoundError;
extern PyObject *PyExc_DBNoSuchFileError;
extern PyObject *PyExc_DBPermissionsError;

extern PyObject *Empty_TUPLE;
extern PyObject *None_PAIR;
extern PyObject *Nil;

extern int recordCount;

PyObject *raiseDBError(int err);
void PyDict_SetItemString_Int(PyObject *dict, char *key, int value);

typedef int (*usercopy_fn)(DBT *, unsigned int, void *, unsigned int,
                           unsigned int);

int _t_db_get(DBT *dbt, int offset, void *data, int len, int mode);
int _t_db_read_record(DBT *dbt, int offset, void *data, int len, int mode);
int _t_db_write_record(DBT *dbt, int offset, void *data, int len, int mode);
int _t_db_read_write_record(DBT *dbt, int offset, void *data, int len,
                            int mode);
int _t_db_discard(DBT *dbt, int offset, void *data, int len, int mode);
int _t_db_put_record(t_db *self, DBT *key, DBT *data, PyObject *txn,
                     int flags);
PyObject *_t_db_make_record(PyObject *types, char *data, int size);
PyObject *_t_db_cursor(t_db *self, PyObject *txn, int flags);
PyObject *_t_store_getTxn(t_store *self);

PyObject *t_cursor_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
PyObject *_t_cursor_dup(t_cursor *self, int flags);
int _t_cursor_close(t_cursor *self);
int _t_cursor_init(t_cursor *self, DB *db, DB_TXN *txn, int flags);
PyObject *t_txn_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int _t_txn_init(t_txn *self, DB_ENV *env, DB_TXN *parent, int flags);
PyObject *t_lock_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int _t_lock_init(t_lock *self, t_env *env, int id, DBT *data,
                 db_lockmode_t mode, int flags);
int _t_lock_put(t_lock *self);

void _init_view(PyObject *m);
void _init_repository(PyObject *m);
void _init_container(PyObject *m);
void _init_sequence(PyObject *m);
void _init_db(PyObject *m);
void _init_cursor(PyObject *m);
void _init_env(PyObject *m);
void _init_txn(PyObject *m);
void _init_lock(PyObject *m);
void _init_record(PyObject *m);
void _init_store(PyObject *m);
