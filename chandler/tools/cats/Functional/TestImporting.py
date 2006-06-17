import osaf.sharing.Sharing as Sharing
import osaf.sharing.ICalendar as ICalendar
import tools.cats.framework.ChandlerTestLib as QAUITestAppLib
from tools.cats.framework.ChandlerTestCase import ChandlerTestCase
import os, sys
import osaf.pim as pim


class TestImporting(ChandlerTestCase):
    
    def startTest(self):
        
        def VerifyEventCreation(title):
            self.logger.startAction("Verify events imported")
            testEvent = self.app_ns.item_named(pim.CalendarEvent, title)
            if testEvent is not None:
                self.logger.endAction(True, "Testing event creation: '%s'" % title)
            else:
                self.logger.endAction(False, "Testing event creation: '%s' not created" % title)
        
            
        path = os.path.join(os.getenv('CHANDLERHOME'),"tools/cats/DataFiles")
        # Upcast path to unicode since Sharing requires a unicode path
        path = unicode(path, sys.getfilesystemencoding())
        share = Sharing.OneTimeFileSystemShare(path, u'importTest.ics', ICalendar.ICalendarFormat, itsView=self.app_ns.itsView)
        
        self.logger.startAction("Import Large Calendar")
        collection = share.get()
        self.app_ns.sidebarCollection.add(collection)
        self.scripting.User.idle()
        self.logger.endAction(True, "Imported calendar")
            
        VerifyEventCreation("Go to the beach")
        VerifyEventCreation("Basketball game")
        VerifyEventCreation("Visit friend")
        VerifyEventCreation("Library")
    
        


    