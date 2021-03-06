#   Copyright (c) 2005-2008 Open Source Applications Foundation
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


#twisted imports
import twisted.internet.reactor as reactor
import twisted.internet.defer as defer
import twisted.mail.imap4 as imap4

#Chandler imports
from osaf.pim.mail import IMAPAccount

#Chandler Mail Service imports
import errors
import constants
import base
from utils import *
import message
import mailworker

__all__ = ['IMAPClient']

"""
    TODO:
    1. Look in to pluging the Python email 3.0 Feedparser in to the
       rawDataReceived method of IMAP4Client for better performance.
       Or Twisted Feedparser (For 1.0). *** By lowering the in memory
       limit the messgeFile IMAP4Client API will be used to create a tmp file.
       This is useful for memory management
    2. Will need to just get the basic headers of subject, message id,
       message size to, from, cc. Then have a callback to sync the rest
       when downloading an individual mail use the feedparser for performance
    3. Could fetch UID's then build a sorted list and use pop to get the newest
       messages first
"""

class FolderVars(base.DownloadVars):
    """
       This class contains the non-persisted
       IMAPFolder variables that are used
       during the downloading of mail from an
       IMAP folder.
    """ 
    def __init__(self):
        super(FolderVars, self).__init__()

        # The C{osaf.pim.mail.IMAPFolder} item
        # that contains the persisted folder info
        self.folderItem   = None

        # The IMAP UID of the last message
        # downloaded from the folder.
        # This is used to cache the highest
        # downloaded message uid up to point
        # just before a commit takes place.
        # At that point the lastUID is saved
        # in the IMAPFolder.lastMessageUID
        # attribute
        self.lastUID = 0

        # The IMAP UID of the last message
        # searched in a folder. This value
        # gets commited in the _getNextFolder
        # method at the end of a search.
        self.lastSearchUID = 0

        # The index position of the
        # IMAP folder in the IMAPAccount.folders
        # sequence.
        self.indexNumber = 0

        # The list of UID's to search
        # for Chandler Headers
        self.searchUIDs = []

        # The list of UID's of messages
        # that contain Chandler Headers
        # and should be downloaded.
        self.foundUIDs  = []

class _TwistedIMAP4Client(imap4.IMAP4Client):
    """
    Overrides C{imap4.IMAP4Client} to add Chandler specific functionality
    including startTLS management and Timeout management.
    """

    def serverGreeting(self, caps):
        """
        This method overrides C{imap4.IMAP4Client}.
        It assigns itself as the protocol for its delegate.

        If caps is None does an explicit request to the
        IMAP server for its capabilities.

        Entry point for STARTTLS logic. Will call delegate.loginClient
        or delegate.catchErrors if an error occurs.

        @param caps: The list of server CAPABILITIES or None
        @type caps: C{dict} or C{None}
        @return C{defer.Deferred}
        """
        if __debug__:
            trace("serverGreeting")

        if caps is None:
            # If no capabilities returned in server greeting then get
            # the server capabilities
            d = self.getCapabilities()

            d.addCallback(self._getCapabilities)
            d.addErrback(self.delegate.catchErrors)
            return None

        self._getCapabilities(caps)
        return None

    def _getCapabilities(self, caps):
        if __debug__:
            trace("_getCapabilities")

        if self.factory.useTLS:
            # The Twisted IMAP4Client will check to make sure the server can STARTTLS
            # and raise an error if it can not
            d = self.startTLS(self.transport.contextFactory.getContext())

            d.addCallback(lambda _: self.delegate.loginClient())
            d.addErrback(self.delegate.catchErrors)
            return None

        if 'LOGINDISABLED' in caps:
            return self._raiseException(
                     errors.IMAPException(constants.MAIL_PROTOCOL_REQUIRES_TLS))

        else:
            # Remove the STARTTLS from capabilities
            self._capCache = disableTwistedTLS(caps)
            self.delegate.loginClient()

    def timeoutConnection(self):
        """
        Called by C{policies.TimeoutMixin} base class.
        The method generates an C{IMAPException} and forward
        to delegate.catchErrors.
        """
        if __debug__:
            trace("timeoutConnection")

        # We have timed out so do not send any more commands to
        # the server just disconnect
        exc = errors.IMAPTimeoutException(constants.MAIL_PROTOCOL_TIMEOUT_ERROR)
        self.factory.timedOut = True
        self._raiseException(exc)

    def _raiseException(self, exception):
        if __debug__:
            trace("_raiseException")

        raised = False

        if self._lastCmd and self._lastCmd.defer is not None:
            d, self._lastCmd.defer = self._lastCmd.defer, None
            d.errback(exception)
            raised = True

        if self.queued:
            for cmd in self.queued:
                if cmd.defer is not None:
                    d, cmd.defer = cmd.defer, d
                    d.errback(exception)
                    raised = True

        if not raised:
            d = defer.Deferred().addErrback(self.delegate.catchErrors)
            d.errback(exception)

    def sendLine(self, line):
        if __debug__ and constants.DEBUG_CLIENT_SERVER:
            txt = ">>> C: %s" % line

            if constants.DEBUG_CLIENT_SERVER == 1:
                self.delegate._saveToBuffer(txt)

            elif constants.DEBUG_CLIENT_SERVER == 2:
                print txt

        return imap4.IMAP4Client.sendLine(self, line)

    def rawDataReceived(self, data):
        if __debug__ and constants.DEBUG_CLIENT_SERVER:
            txt = ">>> S: %s" % data

            if constants.DEBUG_CLIENT_SERVER == 1:
                self.delegate._saveToBuffer(txt)

            elif constants.DEBUG_CLIENT_SERVER == 2:
                print txt

        return imap4.IMAP4Client.rawDataReceived(self, data)

    def lineReceived(self, line):
        if __debug__ and constants.DEBUG_CLIENT_SERVER:
            txt = ">>> S: %s" % line

            if constants.DEBUG_CLIENT_SERVER == 1:
                self.delegate._saveToBuffer(txt)

            elif constants.DEBUG_CLIENT_SERVER == 2:
                print txt

        return imap4.IMAP4Client.lineReceived(self, line)

    def _fetch(self, messages, useUID=0, **terms):
        # The fastmail messaging engine server
        # returns flags on unread messages
        # when a UID FETCH mNum (RFC822) is requested.
        # This is a bug on the twisted side.
        # The twisted IMAP4Server does not have an API
        # for requesting just the FLAGS and the RFC822.
        # This workaround makes that possible.
        # By requesting the FLAGS everytime we avoid
        # the case where the server on its own
        # returns FLAGS on unread messages.
        if 'rfc822' in terms:
            terms['flags'] = True

        return imap4.IMAP4Client._fetch(self, messages, useUID, **terms)

class IMAPClientFactory(base.AbstractDownloadClientFactory):
    """
    Inherits from C{base.AbstractDownloadClientFactory}
    and overides default protocol and exception values
    with IMAP specific values
    """

    protocol  = _TwistedIMAP4Client

    # The exception to raise when an error occurs
    exception = errors.IMAPException


class IMAPClient(base.AbstractDownloadClient):
    """
    Provides support for Downloading mail from an
    IMAP mail 'Inbox' as well as test Account settings.

    This functionality will be enhanced to be a more
    robust IMAP client in the near future
    """

    # Overides default values in base class to provide
    # IMAP specific functionality
    accountType  = IMAPAccount
    clientType   = "IMAPClient"
    factoryType  = IMAPClientFactory
    defaultPort  = 143
    
    def createChandlerFolders(self, callback, reconnect):
        if __debug__:
            trace("createChandlerFolders")

        assert(callback is not None)
        assert(reconnect is not None)

        self.cb = self._createChandlerFolders

        # The method to call in the UI Thread
        # when the testing is complete.
        # This method is called for both success and failure.
        self.callback = callback

        # Tells whether to print status messages
        self.statusMessages = False

        # Tell what method to call on reconnect
        # when a SSL dialog is displayed.
        # When the dialog is shown the
        # protocol code terminates the
        # connection and calls reconnect
        # if the cert has been accepted
        self.reconnect = reconnect

        # Move code execution path from current thread
        # to Reactor Asynch thread
        reactor.callFromThread(self._connectToServer)

    def removeChandlerFolders(self, callback, reconnect):
        if __debug__:
            trace("removeChandlerFolders")

        assert(callback is not None)
        assert(reconnect is not None)

        self.cb = self._removeChandlerFolders

        # The method to call in the UI Thread
        # when the testing is complete.
        # This method is called for both success and failure.
        self.callback = callback

        # Tells whether to print status messages
        self.statusMessages = False

        # Tell what method to call on reconnect
        # when a SSL dialog is displayed.
        # When the dialog is shown the
        # protocol code terminates the
        # connection and calls reconnect
        # if the cert has been accepted
        self.reconnect = reconnect

        # Move code execution path from current thread
        # to Reactor Asynch thread
        reactor.callFromThread(self._connectToServer)

    def _removeChandlerFolders(self, results):
        if __debug__:
            trace("_removeChandlerFolders")
            
        completed = []
        # completed stores a list of successfully completed operations. Each
        # item is a tuple that will look something like:
        #
        # ('deleted', 'Chandler Mail')
        # ('nonexistent', 'Chandler Events')

        d = self._getChandlerFoldersStatus()
        d.addCallback(
            self._cbRemoveChandlerFolders, completed
        ).addErrback(
            self.catchErrors
        )

        return None

    def _cbDeleted(self, folder, completed):
        def cb(imap_goop):
            completed.append(('deleted', folder))
        return cb

    def _addDeleteCallback(self, d, folderPath):
        msgSet = imap4.MessageSet(1, None)
        d.addCallback(lambda x: self.proto.select(folderPath))
        d.addCallback(lambda x: 
                self.proto.addFlags(msgSet, ("\\Deleted",), uid=True))
        d.addCallback(lambda x: self.proto.expunge())
        d.addCallback(lambda x: self.proto.close())
        d.addCallback(lambda x: self.proto.delete(folderPath))
        
    def _deleteOrUnsubscribe(self, responses, status, type, completed):
        #type 0: list
        #type 1: lsub
        d = defer.succeed(1)
 
        for folder in constants.CURRENT_IMAP_FOLDERS:
            folderPath, exists,  subscribed = status[folder]
            
            if type == 0: # LIST output
                if not exists:
                    completed.append(('nonexistent', folder))
                else:
                    self._addDeleteCallback(d, folderPath)
                    d.addCallback(lambda x: self._cbDeleted(folder, completed))
            else:
                if subscribed:
                    d.addCallback(lambda x: self.proto.unsubscribe(folderPath))

        return d

    def _cbRemoveChandlerFolders(self, status, completed):
        d = defer.succeed(1)

        d.addCallback(self._deleteOrUnsubscribe, status, 0, completed)
        
        # When the above callback is done, we want to LSUB the current folders
        # and UNSUBSCRIBE as necessary. Hence the lambda: we will only call
        # self._getListingDeferredList() once the previous callback is done.
        d.addCallback(lambda result: self._getListingDeferredList(
                                            constants.CURRENT_IMAP_FOLDERS, 1, status))

        d.addCallback(self._deleteOrUnsubscribe, status, 1, completed)
        d.addCallback(lambda result: completed)
        d.addCallback(self._folderingFinished, status)
        d.addErrback(self.catchErrors)

        return None

    def _getChandlerFoldersStatus(self):
        if __debug__:
            trace("_getChandlerFoldersStatus")

        #pos 0: The Unicode name of the folder on the IMAP Server.
        #       The values in ALL_IMAP_FOLDERS are of type i18n.Message.
        #       They need to be converted to Unicode to be saved in
        #       the IMAPFolder.folderName attribute of type schema.Text.
        #pos 1: Boolean whether to folder exists on the server already
        #pos 2: Boolean whether the folder is currently subscribe to already
        status = dict((val, [unicode(val), False, False])
                         for val in constants.ALL_IMAP_FOLDERS)

        d = self.proto.list("", "INBOX")
        d.addCallback(self._cbGetChandlerFolderStatus, status)
        d.addErrback(self.catchErrors)

        return d

    def _getListingDeferredList(self, folders, type, status):
        if type == 0:
            method = self.proto.list
        else:
            method = self.proto.lsub
            
        def getDeferred(key):
            mailboxPath = status[key][0]
            return method("", mailboxPath).addCallback(
                        self._updateStatus, status, type, key
                    )

        deferreds = map(getDeferred, folders)

        d = defer.DeferredList(
                deferreds
            ).addCallback(
                lambda x: status
            ).addErrback(
                self.catchErrors
            )
        return d

    def _cbGetChandlerFolderStatus(self, result, status):
        try:
            # results:
            #   0: Tuple of flags on the folder ie. ('\\Marked', '\\HasChildren')
            #   1: The folder delimiter
            #   2: the folder name
            folderFlags, folderDelim, folderName = result[0]

            # Assign the lowercase flags back to
            # the folderFlags variable. This
            # allows a case insensitive compare
            # of flags such as \\NoInferiors.
            folderFlags = map(str.lower, folderFlags)

        except:
            # This error should never be raised but a
            # safeguard is put in place just in case.
            # Raising an IMAPException will result in
            # a clearer error message to the user
            # than just letting the index out of range
            # error be raised and show to the user.
            return self.proto._raiseException(
                   errors.IMAPException(constants.INBOX_LIST_ERROR))

        if not ("\\noinferiors" in folderFlags or \
           "\\noselect" in folderFlags or \
           folderDelim is None or \
           folderDelim.lower() == "nil"):
            # The folder can be created under the INBOX
            for key in constants.ALL_IMAP_FOLDERS:
               status[key][0] = u"INBOX%s%s" % (folderDelim, key)

        return self._getListingDeferredList(constants.ALL_IMAP_FOLDERS, 0, status)

    def _updateStatus(self, results, status, type, key):
        #type 0: list
        #type 1: lsub
        
        folder = status[key]

        if type:
            folder[2] = bool(results) # i.e. results non-empty
        else:
            folder[1] = bool(results)


    def _createChandlerFolders(self, results):
        if __debug__:
            trace("_createChandlerFolders")

        # completed stores a list of successfully completed operations. Each
        # item is a tuple that will look like one of:
        #
        # ('created', 'Chandler Events') # created this mailbox
        # ('renamed', 'Chandler Tasks', 'Chandler Starred') # renamed a mailbox
        # ('exists', 'Chandler Mail') # no action taken b/c mailbox exists already
        completed = []

        d = self._getChandlerFoldersStatus()
        d.addCallback(
            self._cbCreateChandlerFolders, completed,
        ).addErrback(
            self.catchErrors
        )
        return None

    def _renameSucceeded(self, responses, status, src, dest, completed):
        completed.append(('renamed', src, dest))
        # Change the 'created' flags of the mailboxes so that don't attempt
        # to recreate them in self._createOrSubscribe
        status[src][1] = False
        status[dest][1] = True

    def _cbCreateChandlerFolders(self, status, completed):
        d = defer.succeed(1)
        
        starredStatus = status[constants.CHANDLER_STARRED_FOLDER]
        tasksStatus = status[constants.CHANDLER_TASKS_FOLDER]
        
        if tasksStatus[1] and not starredStatus[1]:
            d = self.proto.rename(tasksStatus[0], starredStatus[0])
            d.addCallback(self._renameSucceeded, status, 
                            constants.CHANDLER_TASKS_FOLDER,
                            constants.CHANDLER_STARRED_FOLDER,
                            completed)

        d.addCallback(self._createOrSubscribe, status, 0, completed)
        
        # When the above callback is done, we want to LSUB the current
        # folders and subscribe to them as necessary. Hence the lambda: we
        # will only call self._getListingDeferredList() once the previous
        # callback is done.
        d.addCallback(lambda result: self._getListingDeferredList(
                                            constants.CURRENT_IMAP_FOLDERS, 1, status))

        d.addCallback(self._createOrSubscribe, status, 1, completed)
        d.addCallback(lambda result: completed)
        d.addCallback(self._folderingFinished, status)
        d.addErrback(self.catchErrors)

        return None

    def _cbCreated(self, folder, completed):
        def cb(imap_goop):
            completed.append(('created', folder))
        return cb
        
    def _createOrSubscribe(self, responses, status, type, completed):
        #type 0: list
        #type 1: lsub
        dList = []
        
        for folder in constants.CURRENT_IMAP_FOLDERS:
            folderPath, exists,  subscribed = status[folder]
            
            if type == 0: # LIST output
                if exists:
                    if not any(t[-1] == folder for t in completed):
                        # bypass the case where we renamed this folder already.
                        completed.append(('exists', folder))
                else:
                    dList.append(
                        self.proto.create(
                            folderPath
                        ).addCallback(
                            self._cbCreated(folder, completed)
                        )
                    )
            else:
                if not subscribed:
                    dList.append(self.proto.subscribe(folderPath))

        if dList:
            d = defer.DeferredList(dList)
            d.addErrback(self.catchErrors)
            return d
        else:
            return None

    def _folderingFinished(self, completed, status):
        # Store the value of the calback locally since
        # actionCompleted will set self.callback to None
        cb = self.callback
        self._actionCompleted()

        nameDict = dict((key, value[0]) for key, value in status.iteritems())
        callMethodInUIThread(cb, ( 1, (completed, nameDict)))

    def _loginClient(self):
        """
        Logs a client in to an IMAP servier using the CramMD6, Login, or
        Plain authentication
        """

        if __debug__:
            trace("_loginClient")

        if self.cancel:
            return self._actionCompleted()

        assert self.account is not None

        #Twisted expects 8-bit values so encode the utf-8 username and password
        username = self.account.username.encode("utf-8")

        deferredPassword = self.account.password.decryptPassword()

        def callback(password):
            password = password.encode("utf-8")
            self.proto.registerAuthenticator(imap4.CramMD5ClientAuthenticator(username))
            self.proto.registerAuthenticator(imap4.LOGINAuthenticator(username))

            return self.proto.authenticate(password
                         ).addCallback(self.cb
                         ).addErrback(self.loginClientInsecure, username, password
                         ).addErrback(self.catchErrors)

        deferredPassword.addCallback(callback
                              ).addErrback(self.catchErrors)

        return None


    def loginClientInsecure(self, error, username, password):
        """
        If the IMAP4 Server does not support MD5 or Login authentication
        will attempt to login in via plain text login.

        This method is called as a result of a failure to login
        via an authentication mechanism. If the error.value
        is not of C{imap4.NoSupportAuthentication} then
        there was actually an error such as incorrect username
        or password. In this case the method forward the error to
        self.catchErrors.

        @param error: A Twisted Failure
        @type error: C{failure.Failure}

        @param username: The username to log in with
        @type username: C{string}

        @param password: The password to log in with
        @type password: C{string}
        """

        if __debug__:
            trace("loginClientInsecure")

        if self.cancel:
            return self._actionCompleted()

        error.trap(imap4.NoSupportedAuthentication)

        return self.proto.login(username, password
                    ).addCallback(self.cb
                    ).addErrback(self.catchErrors)


    def _getMail(self, result):
        if __debug__:
            trace("_getMail")

        if self.cancel:
            return self._actionCompleted()

        if self.account.folders.isEmpty():
            # The account is missing the default
            # Inbox IMAPFolder.
            err = constants.IMAP_INBOX_MISSING % \
                          {'accountName': self.account.displayName}

            return self.proto._raiseException(errors.IMAPException(err))

        self.vars = FolderVars()
        self.vars.folderItem = self.account.folders.first()

        d = self.proto.select(self.vars.folderItem.folderName
                   ).addCallback(self._checkForNewMessages
                   ).addErrback(self.catchErrors)

        return None

    def _getNextFolder(self):
        if __debug__:
            trace("_getNextFolder")

        if self.vars.lastSearchUID:
            # If a last search uid was 
            # set for the folder then
            # save this information on the 
            # IMAPFolder item.
            # We only want to commit the last search
            # uid once all searched mail has been 
            # processed. The last search uid differs
            # from lastUID in that the search uid may
            # point to a mail message which was never
            # downloaded since it did not meet the 
            # search criteria. It is important to delay
            # saving of this search uid till the last 
            # possible moment since once commited no
            # mail will be search lower than this uid.
            # This fixes the case where the highest search
            # uid was getting commited but an error or
            # shutdown happened before the action was 
            # completed.
            imapTuple = (self.vars.folderItem.itsUUID,
                         self.vars.lastSearchUID + 1)

            self.mailWorker.queueRequest((mailworker.UID_REQUEST, self,
                                         self.accountUUID, imapTuple))

        i = self.vars.indexNumber + 1

        # Temp variable needed to get the
        # next folder in the sequence
        folder = self.vars.folderItem

        # Free the mem refs of the previous
        # FolderVars instance
        self.vars = None

        # Close the current folder
        d = self.proto.close()

        if i >= len(self.account.folders):
            # All folders for the IMAPAccount have been
            # scanned so call actionCompleted and MailWorker

            # If at least one message was downloaded then
            # queue a DONE_REQUEST so the MailWorker can
            # print the download stats to the status bar
            self.mailWorker.queueRequest((mailworker.DONE_REQUEST, self,
                                          self.accountUUID))

            # Calling _actionCompleted with a False argument
            # keeps the performingAction lock. The completion of
            # processing of the DONE_REQUEST in the MailWorker
            # will result in the performingAction lock being released.
            d.addBoth(lambda x: self._actionCompleted(False))
            return None

        self.vars = FolderVars()
        self.vars.folderItem  = self.account.folders.next(folder)
        self.vars.indexNumber = i

        d.addCallback(lambda x: self.proto.select(self.vars.folderItem.folderName))

        d.addCallback(self._checkForNewMessages)
        d.addErrback(self.catchErrors)

        return None

    def _checkForNewMessages(self, msgs):
        if __debug__:
            trace("_checkForNewMessages")

        #XXX: Need to store and compare UIDVALIDITY.
        #     The issue is what does Chandler do if the
        #     UIDVALIDITY has changed. Not being a
        #     traditional mail client we could not
        #     just refetch the messages since the
        #     Message Items may have changed dramatically
        #     i.e. unstamped as Mail and stamped as an Event
        #     and shared with other users. Or altered as
        #     part of an Edit / Update workflow.
        #     For now UIDVALIDITY will be ignored :(
        #if not msgs['UIDVALIDITY']:
        #    print "server: %s has no UUID Validity:\n%s" % (self.account.host, msgs)

        if self.cancel:
            return self._actionCompleted()

        if msgs['EXISTS'] == 0:
            return self._getNextFolder()

        # Check that we have not already downloaded the max
        # number of messages for the folder
        max = self.vars.folderItem.downloadMax
        downloaded = self.vars.folderItem.downloaded

        if max > 0 and max == downloaded:
            if __debug__:
                trace("Max number of messages %s reached. No new mail will be \
                       downloaded from '%s'" % (max, self.vars.folderItem.displayName))

            return self._getNextFolder()

        self.vars.lastUID = self.vars.folderItem.lastMessageUID

        if not self.vars.lastUID > 0:
           self.vars.lastUID = 1

        msgSet = imap4.MessageSet(self.vars.lastUID, None)

        if self.vars.folderItem.folderType == "CHANDLER_HEADERS":
            return self.proto.fetchUID(msgSet, uid=1
                    ).addCallbacks(self._searchForChandlerMessages,
                                   self.catchErrors)
        else:
            return self.proto.fetchFlags(msgSet, uid=True
                       ).addCallback(self._getMessagesFlagsUID
                       ).addErrback(self.catchErrors)

    def _searchForChandlerMessages(self, msgs):
        if __debug__:
            trace("_searchForChandlerHeaders")

        for uidDict in msgs.values():
           uid = int(uidDict['UID'])

           if uid >= self.vars.lastUID:
               # Microsoft Exchange Server returnes UID's
               # less than the value in self.vars.lastUID.
               # This violates RFC 3501 and results in
               # Chandler messages being re-downloaded on
               # each sync.
               #
               # Exchange Example:
               #     >>> C: 0004 UID FETCH 3:* (UID)
               #     >>> S: * 2 FETCH (UID 2)
               self.vars.searchUIDs.append(uid)

        # Sort the uids since the ordering returned from the
        # dict may not be sequential
        self.vars.searchUIDs.sort()

        size = len(self.vars.searchUIDs)

        if size == 0:
            # There are no uids greater than the lastUID so
            # scan the next folder
            return self._getNextFolder()

        # The last position in the sorted searchUIDs list
        # is the highest uid in the folder.
        # This value will get commited after
        # all processing is done on the folder.
        self.vars.lastSearchUID = self.vars.searchUIDs[size-1]


        # mset will never be None here since the check to
        # make sure the self.vars.searchUIDs list is not
        # empty has already been done a few lines up.
        mset = self._getSearchMessageSet()

        # Find all mail in the folder that contains the header
        # X-Chandler-Mailer: True, does not contain the \Deleted
        # flag and is greater than the IMAP UID of the last
        # message downloaded from the folder.

        query = imap4.Query(header=('X-Chandler-Mailer', 'True'), 
                            undeleted=True, uid=mset)
        start = 0
        end = len(mset)
        total = size

        d = self.proto.search(query, uid=1)

        d.addCallback(self._findChandlerMessages, end, total)
        d.addErrback(self.catchErrors)

        self._printSearchNum(start, end, total)

        return None

    def _printSearchNum(self, start, end, total):
        if self.statusMessages:
            setStatusMessage(constants.IMAP_SEARCH_STATUS %
                  {'accountName': self.account.displayName,
                  'folderDisplayName': self.vars.folderItem.displayName,
                  'start': start,
                  'end': end,
                  'total': total})


    def _findChandlerMessages(self, msgUIDs, start, total):
        if __debug__:
            trace("_findChandlerMessages")

        for msgUID in msgUIDs:
            # Add all messages that match the
            # search criteria to the foundUIDs
            # list.
            self.vars.foundUIDs.append(msgUID)

        mset = self._getSearchMessageSet()

        if mset:
            query = imap4.Query(header=('X-Chandler-Mailer', 'True'), 
                                undeleted=True, uid=mset)

            end = start + len(mset)

            d = self.proto.search(query, uid=1)

            d.addCallback(self._findChandlerMessages, end, total)
            d.addErrback(self.catchErrors)

            self._printSearchNum(start, end, total)

            return None


        # This point is reached when self._getSearchMessageSet()
        # returns None indicating that there are no more message
        # uids to search for Chandler Headers.

        if len(self.vars.foundUIDs) == 0:
            # If the search returned no message uids
            # then have the worker commit the last seen UID
            # for the folder to prevent searching the same
            # messages again.
            return self._getNextFolder()

        # Search found one or more messages containing the
        # Chandler Headers.
        msgSet = imap4.MessageSet()

        for uid in self.vars.foundUIDs:
            msgSet.add(uid)

        # FYI: Since there are messages to download the incrementing of
        # the lastUID to highest uid of the searched messages
        # will automatically get commited.
        d = self.proto.fetchFlags(msgSet, uid=True)

        # The True argument indicates the message UIDs were
        # retrieved from an IMAP Search. This flag
        # tells the _getMessageFlagsUID method to 
        # perform logic specific to the results of a
        # search
        d.addCallback(self._getMessagesFlagsUID, True)
        d.addErrback(self.catchErrors)

        return None

    def _getSearchMessageSet(self):
        size = len(self.vars.searchUIDs)

        if size == 0:
            return None

        num = size > constants.MAX_IMAP_SEARCH_NUM and \
              constants.MAX_IMAP_SEARCH_NUM or \
              size

        mset = imap4.MessageSet()

        for i in xrange(0, num):
            mset.add(self.vars.searchUIDs[i])

        # Reduce the list removing all uids that have been
        # added to the message set
        self.vars.searchUIDs = self.vars.searchUIDs[num:]

        return mset

    def _getMessagesFlagsUID(self, msgs, fromSearch=False):
        if __debug__:
            trace("_getMessagesFlagsUIDS")

        if self.cancel:
            return self._actionCompleted()

        if fromSearch:
            # If this method was called as the
            # result of a search for Chandler
            # Headers then the lastUID will
            # be the highest UID of all messages
            # searched and the delete flag will not
            # be set because the query results exclude
            # deleted messages. In this case don't compare the
            # message UID to the lastUID and don't
            # check if the message has the \Deleted flag set.
            for message in msgs.itervalues():
                self.vars.pending.append([int(message['UID']),
                                          message['FLAGS']])

        else:
            lastUID = self.vars.lastUID

            for message in msgs.itervalues():
                uid = int(message['UID'])

                if uid < lastUID:
                    # If the UID is less than the lastUID
                    # then skip the message
                    continue

                if not "\\Deleted" in message['FLAGS']:
                    self.vars.pending.append([uid, message['FLAGS']])


        self.vars.totalToDownload = len(self.vars.pending)

        if self.vars.totalToDownload == 0:
            return self._getNextFolder()

        max = self.vars.folderItem.downloadMax
        downloaded = self.vars.folderItem.downloaded

        if max > 0 and (self.vars.totalToDownload + downloaded > max):
            # If the number of pending messages exceeds the
            # maximum number of messages that should be downloaded
            # for this folder as specified in c{IMAPFolder.downloadMax}
            # then reduce the pending list to that maximum number.
            #
            # A c{IMAPFolder.downladMax} value <= 0 indicated that
            # there is no limit on the number of messages that
            # can be downloaded from this folder.
            self.vars.pending = self.vars.pending[:max - downloaded]
            self.vars.totalToDownload = len(self.vars.pending)

        if self.statusMessages:
            # This is a PyICU.ChoiceFormat class
            txt = constants.DOWNLOAD_START_MESSAGES.format(
                                           self.vars.totalToDownload)

            setStatusMessage(txt % \
                             {"accountName": self.account.displayName,
                              "numberOfMessages": self.vars.totalToDownload})

        self._getNextMessageSet()

    def _getNextMessageSet(self):
        """
        Overides base class to add IMAP specific logic.

        If the pending queue has one or messages to download
        for n messages up to the dynamically calculated commit number
        fetch the mail from the IMAP server. If no message pending
        calls actionCompleted() to clean up client resources.
        """
        if __debug__:
            trace("_getNextMessageSet")

        if self.cancel:
            return self._actionCompleted()

        self.vars.numToDownload = len(self.vars.pending)

        if self.vars.numToDownload == 0:
            return self._getNextFolder()

        commitNumber = self.calculateCommitNumber()

        if self.vars.numToDownload > commitNumber:
            self.vars.numToDownload = commitNumber

        m = self.vars.pending.pop(0)

        # Set peek=True (RFC3501 BODY.PEEK) to
        # prevent the IMAP server from marking
        # messages as \Seen.
        self.proto.fetchSpecific(str(m[0]), uid=True, peek=True
                      ).addCallback(self._fetchMessage, m
                      ).addErrback(self.catchErrors)

        # Returning None here instead of the deferred prevents
        # deferreds from over flowing the stack and causing a
        # core dump.
        return None


    def _fetchMessage(self, msgs, curMessage):
        if __debug__:
            trace("_fetchMessage")

        if self.cancel:
            return self._actionCompleted()

        msg = msgs.keys()[0]

        #Check if the uid of the message is greater than
        #last message fetched
        if curMessage[0] > self.vars.lastUID:
            self.vars.lastUID = curMessage[0]


        # Store in a local variable the returned
        # server data in the dict for
        # quicker look up and easy reference.
        mArray = msgs[msg][0]

        if str(mArray[3]).upper() == 'UID':
            # The UID information was returned
            # by the server *after* the RFC822 message.
            # Example: Microsoft Exchange IMAP Server
            msg = mArray[2]
        else:
            # The UID information was returned
            # by the server *before* the RFC822 message.
            # Example: Courier IMAP Server
            msg = mArray[4]

        self.vars.messages.append(
                     # Tuple containing
                     #     0: Mail Request
                     #     1: IMAP UID of message
                     (message.previewQuickParse(msg), curMessage[0])
                )

        # this value is used to determine
        # when to post a MAIL_REQUEST to
        # the MailWorker.
        self.vars.numDownloaded += 1

        # This value is used to calculate the
        # commit number
        self.totalDownloaded += 1

        #XXX figure out what to do here
        #if self.vars.folderItem.deleteOnDownload:
        #    # If the user elects to delete mail
        #    # from the IMAP Server that has been
        #    # downloaded to Chandler from this
        #    # IMAP folder then add the message UID
        #    # to the delete list. The \\Deleted flag
        #    # flag will be added to the message on the
        #    # IMAP Server after the corresponding MailStamp
        #    # has been committed to the Repository.
        #    self.vars.delList.append(curMessage[0])

        if self.vars.numDownloaded == self.vars.numToDownload:
            imapFolderInfo = (self.vars.folderItem.itsUUID, 
                              self.vars.lastUID + 1)

            args = self._getStatusStats()
            args["folderDisplayName"] = self.vars.folderItem.displayName

            statusMsg = constants.IMAP_COMMIT_MESSAGES % args

            self._commitMail(statusMsg, imapFolderInfo)

            # Increment the totalDownloaded counter
            # by the number of messages in 
            # the self.vars.messages queue
            self.vars.totalDownloaded = args["end"]
        else:
            m = self.vars.pending.pop(0)

            # Set peek=True (RFC3501 BODY.PEEK) to
            # prevent the IMAP server from marking
            # messages as \Seen.
            d = self.proto.fetchSpecific(str(m[0]), uid=True, peek=True)

            d.addCallback(self._fetchMessage, m)
            d.addErrback(self.catchErrors)

        # Returning None here instead of the Deferred prevents
        # deferreds from over flowing the stack and causing a
        # core dump.
        return None

    def nextAction(self):
        if __debug__:
            trace("nextAction")

        #XXX Don't delete the messages till we are sure they have been
        # commited to Chandler
        #if self.vars.folderItem.deleteOnDownload and len(self.vars.delList):
        #    msgSet = imap4.MessageSet()
        #
        #    for uid in self.vars.delList:
        #        msgSet.add(uid)
        #    self.vars.delList = []
        #
        #    # Since the flags are silent this should never raise an error
        #    d = self.proto.addFlags(msgSet, ("\\Deleted",), uid=True)

        self._nextAction()

        if len(self.vars.pending) == 0:
            # We have downloaded all the pending messages for this folder
            reactor.callLater(0, self._getNextFolder)
        else:
            # There are more messages to download from this folder
            reactor.callLater(0, self._getNextMessageSet)

    def _beforeDisconnect(self):
        """
        Overides base class to send a IMAP 'LOGOUT' command
        before disconnecting from the IMAP server
        """

        if __debug__:
            trace("_beforeDisconnect")

        if self.factory is None or self.proto is None or \
           self.factory.connectionLost or self.factory.timedOut or \
           self.proto.queued is None:
            return defer.succeed(True)

        #XXX Commenting out the code that sends a close IMAP command
        # when an error arises and the self.vars has yet to be reset.
        #if self.vars and self.vars.folderItem:
        #    # If the vars instance is not None and the
        #    # folderItem is not None then a cancel,
        #    # shutdown, or error occurred in which case
        #    # we want to close the open folder
        #    d = self.proto.close()
        #    d.addBoth(lambda x: self.proto.sendCommand(imap4.Command('LOGOUT', \
        #                        wantResponse=('BYE',))))
        #else:
        return self.proto.sendCommand(imap4.Command('LOGOUT', wantResponse=('BYE',)))

