__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2005 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

"""Contains base classes utilized by the Mail Service concrete classes"""
#twisted imports
import twisted.internet.reactor as reactor
import twisted.internet.defer as defer
import twisted.internet.error as error
import twisted.protocols.policies as policies
import twisted.internet.protocol as protocol
import twisted.python.failure as failure
from twisted.internet import threads

#python imports
import logging

#Chandler imports
from repository.persistence.RepositoryError \
    import RepositoryError, VersionConflictError
from repository.persistence.RepositoryView import RepositoryView
import osaf.pim.mail as Mail
from osaf.framework.certstore import ssl
import application.Utility as Utility

#Chandler Mail Service imports
import errors
import constants
from utils import *

"""Call RepositoryView.prune(1000) after commit when the number of
   downloaded messages exceeds PRUNE_MIN"""
PRUNE_MIN = 25


class AbstractDownloadClientFactory(protocol.ClientFactory):
    """ Base class for Chandler download transport factories(IMAP, POP, etc.).
        Encapsulates boiler plate logic for working with Twisted Client Factory
        disconnects and Twisted protocol creation"""

    """Base exception that will be raised on error.
       can be overiden for use by subclasses"""
    exception = errors.MailException

    def __init__(self, delegate):
        """
        @param delegate: A Chandler protocol class containing:
          1. An account object inherited from c{Mail.AccountBase}
          2. A loginClient method implementation callback
          3. A catchErrors method implementation errback
        @type delegate: c{object}

        @return: C{None}
        """

        self.delegate = delegate
        self.connectionLost = False
        self.sendFinished = 0
        self.useTLS = (delegate.account.connectionSecurity == 'TLS')
        self.timeout = delegate.account.timeout
        self.timedOut = False

        retries = delegate.account.numRetries

        assert isinstance(retries, (int, long))
        self.retries = -retries

    def buildProtocol(self, addr):
        """
        Builds a Twisted Protocol instance assigning factory
        and delegate as variables on the protocol instance

        @param addr: an object implementing L{twisted.internet.interfaces.IAddress}

        @return: an object extending  L{twisted.internet.protocol.Protocol}
        """
        p = protocol.ClientFactory.buildProtocol(self, addr)

        """Set up a reference so delegate can call the proto and proto
          can call the delegate.
        """
        p.delegate = self.delegate
        self.delegate.proto = p

        """Set the protocol timeout value to that specified in the account"""
        p.timeout = self.timeout
        p.factory  = self

        return p

    def clientConnectionFailed(self, connector, err):
        """
          Called when a connection has failed to connect.

          @type err: L{twisted.python.failure.Failure}
        """
        self._processConnectionError(connector, err)

    def clientConnectionLost(self, connector, err):
        """
          Called when an established connection is lost.

          @type err: L{twisted.python.failure.Failure}
        """
        self._processConnectionError(connector, err)


    def _processConnectionError(self, connector, err):
        self.connectionLost = True

        if self.retries < self.sendFinished <= 0:
            trace("**Connection Lost** Retrying server. Retry: %s" % -self.retries)

            connector.connect()
            self.retries += 1

        elif self.sendFinished <= 0:
            if err.check(error.ConnectionDone):
                err.value = self.exception(errors.STR_CONNECTION_ERROR)

            self.delegate.catchErrors(err)


class AbstractDownloadClient(object):
    """ Base class for Chandler download transports (IMAP, POP, etc.)
        Encapsulates logic for interactions between Twisted protocols (POP, IMAP)
        and Chandler protocol clients"""


    """Subclasses overide these constants"""
    accountType = Mail.AccountBase
    clientType  = "AbstractDownloadClient"
    factoryType = AbstractDownloadClientFactory
    defaultPort = 0

    def __init__(self, view, account):
        """
        @param view: An Instance of C{RepositoryView}
        @type view: C{RepositoryView}
        @param account: An Instance of C{DownloadAccountBase}
        @type account: C{DownloadAccount}
        @return: C{None}
        """
        assert isinstance(account, self.accountType)
        assert isinstance(view, RepositoryView)

        self.view = view

        """These values exist for life of client"""
        self.accountUUID = account.itsUUID
        self.account = None
        self.currentlyDownloading = False
        self.testing = False

        """These values are reassigned per request"""
        self.factory = None
        self.proto = None
        self.lastUID = 0
        self.totalDownloaded = 0
        self.pruneCounter = 0
        self.pending = []
        self.downloadMax = 0

        """These values are reassigned per fetch"""
        self.numDownloaded = 0
        self.numToDownload = 0

    def getMail(self):
        """Retrieves mail from a download protocol (POP, IMAP)"""
        if __debug__:
            trace("getMail")

        """Move code execution path from current thread
           to Reactor Asynch thread"""
        reactor.callFromThread(self._getMail)


    def testAccountSettings(self):
        """Tests the account settings for a download protocol (POP, IMAP).
           Raises an error if unable to establish or communicate properly
           with the a server.
        """
        if __debug__:
            trace("testAccountSettings")

        self.testing = True

        reactor.callFromThread(self._getMail)

    def _getMail(self):
        if __debug__:
            trace("_getMail")

        if self.currentlyDownloading:
            if self.testing:
                trace("%s currently testing account \ settings" % self.clientType)

            else:
                trace("%s currently downloading mail" % self.clientType)

            return

        self.currentlyDownloading = True

        try:
            self.view.refresh()

        except VersionConflictError, e:
            return self.catchErrors(e)

        except RepositoryError, e1:
            return self.catchErrors(e1)

        """Overidden method"""
        self._getAccount()

        self.factory = self.factoryType(self)
        """Cache the maximum number of messages to download before forcing a commit"""
        self.downloadMax = self.account.downloadMax

        if self.testing:
            """If in testing mode then do not want to retry connection or
               wait a long period for a timeout"""
            self.factory.retries = 0
            self.factory.timeout = constants.TESTING_TIMEOUT

        if self.account.connectionSecurity == 'SSL':
            ssl.connectSSL(self.account.host, self.account.port,
                           self.factory, self.view)
        else:
            ssl.connectTCP(self.account.host, self.account.port,
                           self.factory, self.view)

    def catchErrors(self, err):
        """
        This method captures all errors thrown while in the Twisted Reactor Thread.
        @param err: The error thrown
        @type err: C{failure.Failure} or c{Exception}

        @return: C{None}
        """
        if isinstance(err, failure.Failure):
            err = err.value

        if __debug__:
            trace("catchErrors")


        errorType   = str(err.__class__)
        errorString = err.__str__()

        if isinstance(err, Utility.CertificateVerificationError):
            assert err.args[1] == 'certificate verify failed'

            # Reason why verification failed is stored in err.args[0], see
            # codes at http://www.openssl.org/docs/apps/verify.html#DIAGNOSTICS

            if self.testing:
                reconnect = self.testAccountSettings
            else:
                reconnect = self.getMail

            # Post an asynchronous event to the main thread where
            # we ask the user if they would like to trust this
            # certificate. The main thread will then initiate a retry
            # when the new certificate has been added.
            if err.args[0] in ssl.unknown_issuer:
                displaySSLCertDialog(err.untrustedCertificates[0], reconnect)
            else:
                displayIgnoreSSLErrorDialog(err.untrustedCertificates[0], err.args[0],
                                                  reconnect)

            self._actionCompleted()
            return

        if errorType == errors.M2CRYPTO_CHECKER_ERROR:
            # Post an asynchronous event to the main thread where
            # we ask the user if they would like to continue even though
            # the certificate identifies a different host.
            displayIgnoreSSLErrorDialog(err.pem, errorString,#XXX intl
                                              reconnect)

            self._actionCompleted()
            return


        if self.testing:
            alert(constants.TEST_ERROR, self.account.displayName, errorString)
        else:
            alertMailError(constants.DOWNLOAD_ERROR, self.account, errorString)

        self._actionCompleted()

        if __debug__:
            trace(err)


    def loginClient(self):
        """
        Called after serverGreeting to log in a client to the server via
        a protocol (IMAP, POP)

        @return: C{None}
        """
        return self._loginClient()

    def _loginClient(self):
        """Overide this method to place any protocol specific
           logic to be handle logging in to client
        """

        raise NotImplementedError()

    def _beforeDisconnect(self):
        """Overide this method to place any protocol specific
           logic to be handled before disconnect i.e. send a 'Quit'
           command.
        """

        if __debug__:
            self.printCurrentView("_beforeDisconnect")

        return defer.succeed(True)

    def _disconnect(self, result=None):
        """Disconnects a client from a server.
           Has logic to make sure that the client is actually
           connected.
        """

        if __debug__:
            trace("_disconnect")

        self.factory.sendFinished = 1

        if not self.factory.connectionLost and self.proto is not None:
            self.proto.transport.loseConnection()


    def _commitDownloadedMail(self):
        """Commits mail to the C{Repository}.
           If there are more messages to download
           calls C{_getNextMessageSet} otherwise
           calls C{_actionCompleted} to clean up
           client references
        """
        if __debug__:
            trace("_commitDownloadedMail")

        def _tryCommit():
            try:
                self.view.commit()

                """Prune the view to free up memory if the number downloaded is equal
                   to or exceeds the PRUNE_MIN. If the numDownloaded is less than the
                   download maximum before a commit it means that all messages have been downloaded
                   from the server in which case we prune to free every ounce of memory we can
                   get :)"""

                if self.pruneCounter >= PRUNE_MIN or \
                   self.numDownloaded < self.downloadMax:
                    self.view.prune(1000)

                    if __debug__:
                        trace("Prunning %s messages" % self.pruneCounter)
 
                    """reset the counter"""
                    self.pruneCounter = 0
            except RepositoryError, e:
                #Place holder for commit rollback
                raise e
            except VersionConflictError, e1:
                #Place holder for commit rollback
                raise(e1)

        d = threads.deferToThread(_tryCommit)
        #XXX: May want to handle the case where the Repository fails
        #     to commit. For example, role back transaction or display
        #     Repository error to the user
        d.addCallbacks(lambda _: self._postCommit(), self.catchErrors)

        return d

    def _postCommit(self):
        if __debug__:
            trace("_postCommit")

        msg = constants.DOWNLOAD_MESSAGES % self.totalDownloaded

        NotifyUIAsync(msg)

        """We have downloaded the last batch of messages if the
           number downloaded is less than the max.

           Add a check to make sure the account was not
           deactivated during the last fetch sequesnce.
        """
        if self.numDownloaded < self.downloadMax or not self.account.isActive:
            self._actionCompleted()

        else:
            self.numDownloaded = 0
            self.numToDownload = 0

            self._getNextMessageSet()

    def _getNextMessageSet(self):
        """Overide this to add retrieval of
           message set logic for POP. IMAP, etc
        """
        raise NotImplementedError()

    def _actionCompleted(self):
        """Handles clean up after mail downloaded
           by calling:
               1. _beforeDisconnect
               2. _disconnect
               3. _resetClient
        """

        if __debug__:
            trace("_actionCompleted")

        d = self._beforeDisconnect()
        d.addBoth(self._disconnect)
        d.addCallback(lambda _: self._resetClient())

    def _resetClient(self):
        """Resets Client object state variables to
           default state.
        """

        if __debug__:
            trace("_resetClient")

        """Release the currentlyDownloading lock"""
        self.currentlyDownloading = False

        """Reset testing to False"""
        self.testing = False

        """Clear out per request values"""
        self.factory         = None
        self.proto           = None
        self.lastUID         = 0
        self.totalDownloaded = 0
        self.pruneCounter    = 0
        self.pending         = []
        self.downloadMax     = 0

        self.numToDownload  = 0
        self.numDownloaded  = 0

    def _getAccount(self):
        """Overide this method to add custom account
           look up logic. Accounts can not be passed across
           threads so the C{UUID} must be used to fetch the 
           account's data
        """
        raise NotImplementedError()
