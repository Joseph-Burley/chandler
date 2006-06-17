import tools.cats.framework.ChandlerTestLib as QAUITestAppLib
from tools.cats.framework.ChandlerTestCase import ChandlerTestCase
import osaf.framework.scripting as scripting
from i18n.tests import uw

class TestNewCollection(ChandlerTestCase):
    
    def startTest(self):
            
        # action
        col = QAUITestAppLib.UITestItem("Collection", self.logger)
        # verification
        col.Check_CollectionExistence("Untitled")
        
        # action
        col.SetDisplayName(uw("Meeting"))
        # verification
        col.Check_CollectionExistence(uw("Meeting"))
        
        # action
        note = QAUITestAppLib.UITestItem("Note", self.logger)
        note.AddCollection(uw("Meeting"))
        # verification
        note.Check_ItemInCollection(uw("Meeting"))
        
        # Bug 5803, make sure items in collections that change to not mine
        # are really not in the All collection, and similarly that events
        # created after the collection becomes not mine are truly not mine
    
        sidebar = QAUITestAppLib.App_ns.sidebar
    
        # select the Meeting collection
        scripting.User.emulate_sidebarClick(sidebar, uw('Meeting'))
    
        # Switch to the Calendar View
        QAUITestAppLib.App_ns.appbar.press(name="ApplicationBarEventButton")
        
        # ... idle() so the app can handle changes
        QAUITestAppLib.scripting.User.idle()
    
        beforeChangeEvent = QAUITestAppLib.UITestItem("Event", self.logger)
        beforeChangeEvent.AddCollection(uw("Meeting"))
        beforeChangeEvent.Check_ItemInCollection(uw("Meeting"), expectedResult=True)
        beforeChangeEvent.Check_ItemInCollection("All", expectedResult=True)
        
        # Change Meeting to stop being in mine
        sidebar.onToggleMineEvent(QAUITestAppLib.App_ns.ToggleMineItem.event)
        
        afterChangeEvent = QAUITestAppLib.UITestItem("Event", self.logger)
        afterChangeEvent.AddCollection(uw("Meeting"))
    
        # both events should be in Meeting and not in All
        beforeChangeEvent.Check_ItemInCollection(uw("Meeting"), expectedResult=True)
        beforeChangeEvent.Check_ItemInCollection("All", expectedResult=False)
    
       afterChangeEvent.Check_ItemInCollection(uw("Meeting"), expectedResult=True)
        afterChangeEvent.Check_ItemInCollection("All", expectedResult=False)
