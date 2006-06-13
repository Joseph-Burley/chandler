import tools.cats.framework.ChandlerTestLib as QAUITestAppLib
from tools.cats.framework.ChandlerTestCase import ChandlerTestCase
import wx

class TestVisibleHouse(ChandlerTestCase):

    def startTest(self):
    
        # Find all the children of the Visible Hours menu
        eventsToTest = list(
            block.event for block in QAUITestAppLib.App_ns.VisibleHoursMenu.childrenBlocks
            if block.hasLocalAttributeValue('event') # ... exclude separators
            and block.event.visibleHours > 0 # ... and the "auto" item
        )
        
        
        for event in eventsToTest:
            name = event.blockName
            self.logger.startAction(name)
    
            # Post the visible hours event... doesn't seem to be
            # a straightforward way to do this
            QAUITestAppLib.App_ns.MainView.onVisibleHoursEvent(event)
            
            # Allow the UI to refresh
            QAUITestAppLib.scripting.User.idle()
            
            # Figure out how many hours the TimedEvents widget is
            # displaying
            widget = QAUITestAppLib.App_ns.TimedEvents.widget
            rect = widget.GetClientRect()
            relativeTime = widget.getRelativeTimeFromPosition(
                              None, wx.Point(0, rect.height))
            widgetHours = int((float(relativeTime.seconds)/3600.0) + 0.5)
            
            
            # ... and double-check it's working
            if widgetHours != event.visibleHours:
                self.logger.endAction(False, "Expected %s visible hours, got %s" %
                                     (event.visibleHours, widgetHours))
            else:
                self.logger.endAction(True, "Number of hours is correct")
    
