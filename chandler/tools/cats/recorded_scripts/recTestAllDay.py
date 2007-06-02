import wx, osaf
from osaf.framework.script_recording.script_lib import ProcessEvent, VerifyOn

def run():
    if wx.Platform == '__WXGTK__':
        return
    
    VerifyOn ()
    ProcessEvent (wx.CommandEvent, {'associatedBlock':'NewCollectionItem', 'eventType':wx.EVT_MENU, 'sentTo':'MainFrame'}, {})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'newFocusWindow':-309, 'newFocusWindowClass':osaf.framework.attributeEditors.AETypeOverTextCtrl.AENonTypeOverTextCtrl}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':148, 'm_y':-128, 'UnicodeKey':84})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'Untitled'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':148, 'm_y':-128, 'UnicodeKey':116})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u't'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':148, 'm_y':-128, 'UnicodeKey':69})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u't'}, {'m_rawCode':101, 'm_keyCode':101, 'm_x':148, 'm_y':-128, 'UnicodeKey':101})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'te'}, {'m_rawCode':83, 'm_keyCode':83, 'm_x':148, 'm_y':-128, 'UnicodeKey':83})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'te'}, {'m_rawCode':115, 'm_keyCode':115, 'm_x':148, 'm_y':-128, 'UnicodeKey':115})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'tes'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':148, 'm_y':-128, 'UnicodeKey':84})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'tes'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':148, 'm_y':-128, 'UnicodeKey':116})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'test'}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':148, 'm_y':-128, 'UnicodeKey':16})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'test'}, {'m_rawCode':65, 'm_keyCode':65, 'm_shiftDown':True, 'm_x':148, 'm_y':-128, 'UnicodeKey':65})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'test'}, {'m_rawCode':65, 'm_keyCode':65, 'm_shiftDown':True, 'm_x':148, 'm_y':-128, 'UnicodeKey':65})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testA'}, {'m_rawCode':76, 'm_keyCode':76, 'm_x':148, 'm_y':-128, 'UnicodeKey':76})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testA'}, {'m_rawCode':108, 'm_keyCode':108, 'm_x':148, 'm_y':-128, 'UnicodeKey':108})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAl'}, {'m_rawCode':76, 'm_keyCode':76, 'm_x':148, 'm_y':-128, 'UnicodeKey':76})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAl'}, {'m_rawCode':108, 'm_keyCode':108, 'm_x':148, 'm_y':-128, 'UnicodeKey':108})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAll'}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':148, 'm_y':-128, 'UnicodeKey':16})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAll'}, {'m_rawCode':68, 'm_keyCode':68, 'm_shiftDown':True, 'm_x':148, 'm_y':-128, 'UnicodeKey':68})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAll'}, {'m_rawCode':68, 'm_keyCode':68, 'm_shiftDown':True, 'm_x':148, 'm_y':-128, 'UnicodeKey':68})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAllD'}, {'m_rawCode':65, 'm_keyCode':65, 'm_x':148, 'm_y':-128, 'UnicodeKey':65})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAllD'}, {'m_rawCode':97, 'm_keyCode':97, 'm_x':148, 'm_y':-128, 'UnicodeKey':97})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAllDa'}, {'m_rawCode':89, 'm_keyCode':89, 'm_x':148, 'm_y':-128, 'UnicodeKey':89})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAllDa'}, {'m_rawCode':121, 'm_keyCode':121, 'm_x':148, 'm_y':-128, 'UnicodeKey':121})
    ProcessEvent (wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':'__FocusWindow__', 'lastWidgetValue':u'testAllDay'}, {'m_rawCode':13, 'm_keyCode':13, 'm_x':148, 'm_y':-128, 'UnicodeKey':13})
    ProcessEvent (wx.MouseEvent, {'associatedBlock':'ApplicationBar', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':'ApplicationBar', 'newFocusWindow':-219, 'newFocusWindowClass':wx.Window, 'lastWidgetValue':u'testAllDay'}, {'m_leftDown':True, 'm_x':290, 'm_y':17})
    ProcessEvent (wx.MouseEvent, {'associatedBlock':'ApplicationBar', 'eventType':wx.EVT_LEFT_UP, 'sentTo':'ApplicationBar'}, {'m_x':290, 'm_y':17})
    ProcessEvent (wx.CommandEvent, {'associatedBlock':'ApplicationBarNewButton', 'eventType':wx.EVT_MENU, 'sentTo':'ApplicationBar'}, {})
    ProcessEvent (wx.MouseEvent, {'associatedBlock':'EditAllDay', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':'EditAllDay', 'newFocusWindow':-305, 'newFocusWindowClass':wx.Window}, {'m_leftDown':True, 'm_x':3, 'm_y':4})
    ProcessEvent (wx.MouseEvent, {'associatedBlock':'EditAllDay', 'eventType':wx.EVT_LEFT_UP, 'sentTo':'EditAllDay', 'newFocusWindow':'EditAllDay', 'newFocusWindowClass':osaf.framework.attributeEditors.AttributeEditors.AECheckBox, 'lastWidgetValue':False}, {'m_x':3, 'm_y':4})
    ProcessEvent (wx.CommandEvent, {'associatedBlock':'EditAllDay', 'eventType':wx.EVT_CHECKBOX, 'sentTo':'EditAllDay', 'lastWidgetValue':True}, {})
