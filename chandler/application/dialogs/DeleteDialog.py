#   Copyright (c) 2003-2006 Open Source Applications Foundation
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

import wx
import logging
import os, sys
from application import schema, Globals
from i18n import ChandlerMessageFactory as _
from application.dialogs.RecurrenceDialog import getProxy

logger = logging.getLogger(__name__)

REMOVE_NORMAL           = 1
DELETE_DASHBOARD        = 2
DELETE_LAST             = 3
IN_READ_ONLY_COLLECTION = 4
READ_ONLY_SELECTED      = 5


DELETE_STATES = (DELETE_DASHBOARD, DELETE_LAST)

# structure is [itemState][cardinality](bold text, normal text)
dialogTextData = {
    DELETE_DASHBOARD :
        { 'single' : (_(u""), _(u"Removing '%(itemName)s' from the Dashboard will move it to the Trash.")),
          'multi'  : (_(u""), _(u"Removing '%(itemName)s' from the Dashboard will move it to the Trash."))},
    DELETE_LAST :
        { 'single' : (_(u"This is your only instance of '%(itemName)s'."),
                      _(u"Removing it from '%(collectionName)s' will move it to the Trash.")),
          'multi'  : (_(u"This is your only instance of '%(itemName)s'."),
                      _(u"Removing it from '%(collectionName)s' will move it to the Trash."))},
    IN_READ_ONLY_COLLECTION :
        { 'single' : (_(u"Read-only item"),
                      _(u"You cannot delete '%(itemName)s'. "
                        u"It belongs to the read-only collection '%(readOnlyCollectionName)s'.")),
          'multi'  : (_(u"%(count)s Read-only items"),
                      _(u"You cannot delete '%(itemName)s'. "
                        u"It belongs to the read-only collection '%(readOnlyCollectionName)s'."))},    
    READ_ONLY_SELECTED :
        { 'single' : (_(u"Read-only collection"),
                      _(u"You cannot make changes to '%(collectionName)s'")),
          'multi'  : (_(u"Read-only collection"),
                      _(u"You cannot make changes to '%(collectionName)s'"))},
}

def GetReadOnlyCollection(item, view):
    """Return the first read-only collection the item is in, or None."""
    app_ns = schema.ns('osaf.app', view)
    pim_ns = schema.ns('osaf.pim', view)
    allCollection = pim_ns.allCollection
    
    sidebarCollections = app_ns.sidebarCollection
    
    memberItem = getProxy(u'ui', item).getMembershipItem()
    for collection in [col for col in sidebarCollections if col.readOnly]:
        if memberItem in collection:
            return collection
    return None

def GetItemRemovalState(selectedCollection, item, view):
    """
    Determine how an item that's supposed to be removed ought to be handled.

    It may be simply removed, or its collection membership may indicate that
    it should be deleted, or it could be treated as read-only.
    
    """
    app_ns = schema.ns('osaf.app', view)
    pim_ns = schema.ns('osaf.pim', view)
    allCollection = pim_ns.allCollection
    
    sidebarCollections = app_ns.sidebarCollection
    readonlyCollections = [col for col in sidebarCollections
                           if col.readOnly]

    # you can always remove from the trash
    if selectedCollection is pim_ns.trashCollection:
        return REMOVE_NORMAL

    elif selectedCollection in readonlyCollections:
        return READ_ONLY_SELECTED

    else:
        memberItem = getProxy(u'ui', item).getMembershipItem()
        if (selectedCollection is allCollection and
            memberItem in pim_ns.mine):
            # Items in the dashboard can't be removed if they're
            # automatically included from a mine collection
            if GetReadOnlyCollection(item, view) is None:
                return DELETE_DASHBOARD
            else:
                return IN_READ_ONLY_COLLECTION
        else:
            if len(memberItem.appearsIn) > 1:
                return REMOVE_NORMAL
            else:
                return DELETE_LAST

def ShowDeleteDialog(parent, view=None, selectedCollection=None,
                     itemsAndStates=None, originalAction='remove', modal=True):
    filename = 'DeleteDialog.xrc'
    xrcFile = os.path.join(Globals.chandlerDirectory,
                           'application', 'dialogs', filename)
    #[i18n] The wx XRC loading method is not able to handle raw 8bit paths
    #but can handle unicode
    xrcFile = unicode(xrcFile, sys.getfilesystemencoding())
    resources = wx.xrc.XmlResource(xrcFile)
    win = DeleteDialog(parent,
                       resources=resources,
                       view=view,
                       selectedCollection=selectedCollection,
                       originalAction=originalAction,
                       modal=modal,
                       itemsAndStates=itemsAndStates)
    
    win.CenterOnScreen()
    if modal:
        return win.ShowModal()
    else:
        win.Show()
        return win

class DeleteDialog(wx.Dialog):

    def __init__(self, parent, resources=None, view=None, 
                 selectedCollection=None, originalAction='remove', modal=True,
                 itemsAndStates=None):

        self.resources = resources
        self.view = view
        self.parent = parent
        self.selectedCollection = selectedCollection
        self.modal = modal
        self.itemsAndStates = itemsAndStates
        self.originalAction = originalAction
        
        # Apply to all checkbox states
        self.lastItemApplyAll   = False
        self.readOnlyApplyAll   = False
        self.dashboardRemoveAll = False

        # count whether Apply to alls should be shown
        self.countDict = {DELETE_DASHBOARD        : 0, 
                          DELETE_LAST             : 0,
                          IN_READ_ONLY_COLLECTION : 0,
                          READ_ONLY_SELECTED      : 0}

        for item, state in itemsAndStates:
            self.countDict[state] += 1

        # the item in itemsAndStates being worked with, incremented by
        # ProcessNextItem
        self.itemNumber = -1

        pre = wx.PreDialog()
        self.resources.LoadOnDialog(pre, parent, "DeleteDialog")
        self.PostCreate(pre)

        plural = len(itemsAndStates) > 1
        textData = {'collectionName' : selectedCollection.displayName}
        if originalAction == 'remove':
            if plural:
                title = _(u"Remove items from %(collectionName)s" % textData)
            else:
                title = _(u"Remove item from %(collectionName)s" % textData)
        else:
            if plural:
                title = _(u"Move items to trash")
            else:
                title = _(u"Move item to trash")
        
        self.SetTitle(title)

        self.boldText = wx.xrc.XRCCTRL(self, "BoldText")
        self.normalText = wx.xrc.XRCCTRL(self, "NormalText")        
        self.checkbox = wx.xrc.XRCCTRL(self, "ApplyAll")
        
        boldSize = self.Font.GetPointSize() + 1
        bold = wx.Font(boldSize, wx.NORMAL, wx.NORMAL, wx.BOLD)        
        self.boldText.SetFont(bold)

        self.Bind(wx.EVT_BUTTON, self.ProcessOK, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnDone, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.ProcessDelete,
                  id=wx.xrc.XRCID("MoveToTrash"))

        self.Fit()

        self.ProcessNextItem()
        

    def ProcessNextItem(self):
        while True:
            self.itemNumber += 1
            if self.itemNumber >= len(self.itemsAndStates):
                self.OnDone()
            else:
                item, state = self.itemsAndStates[self.itemNumber]
                
                # ignoring applyToAll for now
                if state == DELETE_DASHBOARD:
                    if self.dashboardRemoveAll:
                        self.DeleteItem()
                        continue
                    else:
                        self.DeletePrompt()
                elif state == DELETE_LAST:
                    if self.lastItemApplyAll:
                        self.DeleteItem()
                        continue
                    else:
                        self.DeletePrompt()
                elif state == IN_READ_ONLY_COLLECTION:
                    if self.readOnlyApplyAll:
                        continue
                    else:
                        self.ReadOnlyPrompt()
                else:
                    self.ReadOnlyPrompt()
            break

    def GetTextDict(self):
        item, state = self.itemsAndStates[self.itemNumber]
        textDict = dict(collectionName = self.selectedCollection.displayName,
                        itemName       = item.displayName,
                        count          = self.countDict[state])
        if state == IN_READ_ONLY_COLLECTION:
            readOnlyCollection = GetReadOnlyCollection(item, self.view)
            textDict['readOnlyCollectionName'] = readOnlyCollection.displayName
        return textDict

    def SetText(self):
        item, state = self.itemsAndStates[self.itemNumber]
        textDict = self.GetTextDict()
        cardinality = self.countDict[state] > 1 and 'multi' or 'single'
        boldText, normalText = dialogTextData[state][cardinality]

        self.boldText.SetLabel(boldText     % textDict)
        self.normalText.SetLabel(normalText % textDict)
        self.boldText.Wrap(350)
        self.normalText.Wrap(350)
        
        if boldText == '':
            self.boldText.Hide()
        else:
            self.boldText.Show()
        
    def ReadOnlyPrompt(self):
        self.AdjustButtons()

        item, state = self.itemsAndStates[self.itemNumber]
        cardinality = self.countDict[state] > 1 and 'multi' or 'single'
        
        
        if state == IN_READ_ONLY_COLLECTION and cardinality == 'multi':
            self.checkbox.Show()
            self.checkbox.SetValue(False)
        else:
            self.checkbox.Hide()

        self.SetText()
            
        wx.xrc.XRCCTRL(self, "wxID_OK").SetFocus()
        self.Fit()
        wx.Yield()

    def DeletePrompt(self):
        self.AdjustButtons()

        item, state = self.itemsAndStates[self.itemNumber]
        cardinality = self.countDict[state] > 1 and 'multi' or 'single'
        
        if cardinality == 'multi':
            self.checkbox.Show()
            self.checkbox.SetValue(False)
        else:
            self.checkbox.Hide()
        
        self.SetText()

        wx.xrc.XRCCTRL(self, "MoveToTrash").SetFocus()
        self.Fit()
        wx.Yield()

    def HandleApplyToAll(self):
        state = self.itemsAndStates[self.itemNumber][1]
        self.countDict[state] -= 1
        if self.checkbox.IsShown() and self.checkbox.GetValue():
            if state == DELETE_DASHBOARD:
                self.dashboardRemoveAll = True
            elif state == DELETE_LAST:
                self.lastItemApplyAll = True
            elif state == IN_READ_ONLY_COLLECTION:
                self.readOnlyApplyAll = True

    def ProcessOK(self, evt):
        if self.itemsAndStates[self.itemNumber][1] == READ_ONLY_SELECTED:
            # only prompt once if the selected collection is read only
            self.OnDone()
        else:
            self.HandleApplyToAll()
            self.ProcessNextItem()

    def DeleteItem(self):
        trash = schema.ns('osaf.pim', self.view).trashCollection
        proxiedItem = getProxy(u'ui', self.itemsAndStates[self.itemNumber][0])
        proxiedItem.addToCollection(trash)

    def ProcessDelete(self, evt=None):
        self.DeleteItem()
        self.HandleApplyToAll()
        self.ProcessNextItem()

    def OnDone(self, evt=None):
        if self.modal:
            self.EndModal(False)
        self.Destroy()

    def AdjustButtons(self):
        state = self.itemsAndStates[self.itemNumber][1]
        if state in DELETE_STATES:
            wx.xrc.XRCCTRL(self, "wxID_CANCEL").Show()
            wx.xrc.XRCCTRL(self, "MoveToTrash").Show()
            wx.xrc.XRCCTRL(self,     "wxID_OK").Hide()
        else:
            wx.xrc.XRCCTRL(self, "wxID_CANCEL").Hide()
            wx.xrc.XRCCTRL(self, "MoveToTrash").Hide()
            wx.xrc.XRCCTRL(self,     "wxID_OK").Show()

    def _resize(self):
        self.Fit()
