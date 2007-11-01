#   Copyright (c) 2003-2007 Open Source Applications Foundation
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

from application.Plugins import PluginMenu, DemoMenu
from application import schema
import wx
from colorsys import hsv_to_rgb
from osaf.pim.structs import ColorType
from osaf.framework.blocks import ColorEvent

def makeColorMenuItems (parcel, theClass, hues, prefix=""):
    """
    dynamically creates an array of type 'theClass' based on a list of colors
    """
    menuItems = []
    
    # make sure that all the events end up in the main parcel
    parcelLocation = "osaf.views.main"
    mainParcel = schema.parcel_for_module (parcelLocation, parcel.itsView)
    nameSpace = schema.ns (parcelLocation, parcel.itsView)

    for shortName, title, hue in hues:
        
        eventName = shortName + 'CollectionColor'
        colorEvent = getattr (nameSpace, eventName, None)
        if colorEvent is None:
            rgb = hsv_to_rgb(hue/360.0, 0.5, 1.0)
            rgb = [int(c*255) for c in rgb] + [255]
    
            colorEvent = ColorEvent.template(
                eventName,
                dispatchToBlockName = 'Sidebar',
                color = ColorType (*rgb),
                methodName = 'onCollectionColorEvent').install (mainParcel)

        menuItem = theClass.template(
            prefix + shortName + 'ColorItem',
            title = title, # XXX No keyboard shortcuts
            icon = shortName + "MenuIcon.png",
            menuItemKind = "Check",
            event = colorEvent)
        menuItems.append (menuItem)

    return menuItems

def makeMainMenus(parcel):

    from osaf.framework.blocks import Menu, MenuItem
    from osaf.framework.blocks.calendar import VisibleHoursEvent
    from i18n import ChandlerMessageFactory as _
    from osaf import messages
    from osaf import usercollections
    from itertools import chain

    if wx.Platform == '__WXMAC__':
        # L10N: Keyboard shortcut to remove an
        # Item from a collection on OS X
        platform_remove = _(u'Back')
        # L10N: Keyboard shortcut to delete (move Item
        #       to Trash) on OS X.
        platform_delete = _(u'Ctrl+Back')
    else:
        # L10N: Keyboard shortcut to remove an
        # Item from a collection on Windows and Linux
        platform_remove = _(u'Del')
        # L10N: Keyboard shortcut to delete (move Item
        #       to Trash) on Windows and Linux.
        platform_delete = _(u'Ctrl+Del')

    
    def makeVisibleHourMenuItems(parcel):
        """
        Create the 'Visible Hours' submenu. Should look like:
        
        Automatic
        ---------
        5 hours
        6 hours

        etc..
        """
        menuItems = []

        hoursText = {
            # L10N: The number of visible hours to display in the Calendar week view
            5: _(u"&5 hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            6: _(u"&6 hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            7: _(u"&7 hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            8: _(u"&8 hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            9: _(u"&9 hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            10: _(u"&10 hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            11: _(u"11 &hours"),
            # L10N: The number of visible hours to display in the Calendar week view
            12: _(u"12 h&ours"),
            # L10N: The number of visible hours to display in the Calendar week view
            18: _(u"18 ho&urs"),
            # L10N: The number of visible hours to display in the Calendar week view
            24: _(u"&24 hours")
        }

        # include '-1' in the list of hours
        for hour in chain([-1], xrange(5, 13), [18], [24]):

            # create the event that will fire. Note that all events on
            # the same method
            eventName = 'VisibleHour' + str(hour)
            event = \
                VisibleHoursEvent.template(eventName,
                                           methodName = 'onVisibleHoursEvent',
                                           visibleHours = hour)
            event = event.install(parcel)

            # now create the menuitem itself
            if hour == -1:
                title = _(u"&Default")
            else:
                title = hoursText[hour]

            menuItem = MenuItem.template(eventName + 'Item',
                                         title = title,
                                         menuItemKind = "Check",
                                         event = event)
            menuItems.append(menuItem)

            # add a separator after 'Automatic'
            if hour == -1:
                menuItem = MenuItem.template('VisibleHourSeparator',
                                             menuItemKind="Separator")
                menuItems.append(menuItem)

        return menuItems
                                         

    repositoryView = parcel.itsView
    main = schema.ns("osaf.views.main", repositoryView)
    globalBlocks = schema.ns("osaf.framework.blocks", repositoryView)
    calBlocks = schema.ns("osaf.framework.blocks.calendar", repositoryView)

    fileMenu =  Menu.template('FileMenu',
                title = _(u'&File'),
                childBlocks = [
                    MenuItem.template('ImportICalendarItem',
                        event = main.ImportICalendar,
                        title = _(u'&Import Tasks and Events from an iCalendar file'),
                        helpString = _(u'Import iCalendar file')),
                    MenuItem.template('ExportICalendarItem',
                        event = main.ExportICalendar,
                        title = _(u'&Export .ics Calendar...'),
                        helpString = _(u'Export Tasks and Events to an iCalendar file')),
                    MenuItem.template('FileSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('DumpToFileItem',
                        event = main.DumpToFile,
                        title = _(u'E&xport Collections and Settings...'),
                        helpString = _(u'Export your data to move to a new version of Chandler')),
                    MenuItem.template('ReloadFromFileItem',
                        event = main.ReloadFromFile,
                        title = _(u'&Reload Collections and Settings...'),
                        helpString = _(u'Reload your data to move to a new version of Chandler')),
                    MenuItem.template('FileSeparator2',
                        menuItemKind = 'Separator'),
                    MenuItem.template('PrefsAccountsItem',
                        event = main.EditAccountPreferences,
                        title = _(u'&Accounts...'),
                        helpString = messages.ACCOUNT_PREFERENCES),
                    MenuItem.template('ProxyConfigItem',
                        event = main.ConfigureProxies,
                        title = _(u'&Configure HTTP Proxy...'),
                        helpString = _(u'Configure HTTP Proxy')),
                    MenuItem.template('ProtectPasswordsItem',
                        event = main.ProtectPasswords,
                        title = _(u'Protect Pass&words...'),
                        helpString = _(u'Protect your account passwords with a master password')),
                    MenuItem.template('LocalePickerItem',
                        event = main.LocalePicker,
                        title = _(u'Swi&tch Language...'),
                        helpString = _(u'Select the language for Chandler')),
                    MenuItem.template('FileSeparator3',
                        menuItemKind = 'Separator'),
                    Menu.template('SyncMenu',
                        title = _(u'S&ync'),
                        childBlocks = [
                            MenuItem.template('SyncCollectionItem',
                                event = main.SyncCollection,
                                title = _(u'Sync'),
                                helpString = _(u"Sync selected collection")),
                            MenuItem.template('SyncAllItem',
                                event = main.SyncAll,
                                title = _(u"&All"),
                                helpString = _(u'Sync mail and all shared collections')),
                            MenuItem.template('SyncIMAPItem',
                                event = main.GetNewMail,
                                title = _(u'&Mail'),
                                helpString = _(u'Sync mail')),
                            MenuItem.template('SyncWebDAVItem',
                                event = main.SyncWebDAV,
                                title = _(u'&Shares'),
                                helpString = _(u'Sync all shared collections')),
                            MenuItem.template('SyncPrefsItem',
                                event = main.SyncPrefs,
                                title = _(u'Set Auto-s&ync...'),
                                helpString = _(u'Set auto-sync intervals')),
                            ]), # Menu SyncMenu
                    Menu.template('OfflineMenu',
                        title = _(u'Suspend syncin&g'),
                        childBlocks = [
                            MenuItem.template('TakeOnlineOfflineItem',
                                event = main.TakeOnlineOffline,
                                title = _(u'Suspend Syncing'),
                                menuItemKind = 'Check',
                                helpString = _(u"Take mail and shared collections offline or online")),
                            MenuItem.template('AllOfflineItem',
                                event = main.TakeAllOnlineOffline,
                                menuItemKind = 'Check',
                                title = _(u'&All'),
                                helpString = _(u'Take mail and shared collections offline or online')),
                            MenuItem.template('TakeMailOnlineOfflineItem',
                                event = main.TakeMailOnlineOffline,
                                menuItemKind = 'Check',
                                title = _(u'&Mail'),
                                helpString = _(u'Take mail offline or online')),
                            MenuItem.template('SharesOfflineItem',
                                event = main.TakeSharesOnlineOffline,
                                title = _(u'&Shares'),
                                helpString = _(u'Take shared collections offline or online')),
                            ]), # Menu OfflineMenu              
                    MenuItem.template('FileSeparator4',
                        menuItemKind = 'Separator'),
                    MenuItem.template('EnableTimezonesItem',
                        event = main.EnableTimezones,
                        title = _(u'Use Time &zones'),
                        menuItemKind = 'Check',
                        helpString = _(u'Turn on time zone support')),
                    MenuItem.template('FileSeparator5',
                        menuItemKind = 'Separator'),
                    MenuItem.template('PrintPreviewItem',
                        event = globalBlocks.PrintPreview,
                        title = _(u'Print Pre&view'),
                        wxId = wx.ID_PREVIEW),
                    MenuItem.template('PageSetupItem',
                        event = globalBlocks.PageSetup,
                        title = _(u'Page Set&up...'),
                        # L10N: Keyboard shortcut to launch Printing
                        #       Page Setup.
                        accel = _(u'Shift+Ctrl+P')),
                    MenuItem.template('PrintItem',
                        event = globalBlocks.Print,
                        title = _(u'&Print...'),
                        # L10N: Keyboard shortcut for Printing.
                        accel = _(u'Ctrl+P'),
                        helpString = _(u'Print the selected collection'),
                        wxId = wx.ID_PRINT),
                    MenuItem.template('FileSeparator6',
                        menuItemKind = 'Separator'),
                    MenuItem.template('CommitView',
                        event = globalBlocks.CommitView,
                        title = _(u'&Save Changes'),
                        # L10N: Keyboard shortcut to save changes.
                        accel = _(u'Ctrl+S'),
                        wxId = wx.ID_SAVE),
                    ])

    if wx.Platform != '__WXMAC__':
        fileMenu.attrs['childBlocks'].append(MenuItem.template('QuitItem',
                                                        event=globalBlocks.Quit,
                                                        title = _(u'&Quit'),
                                                        # L10N: Keyboard shortcut to quit Chandler.
                                                        accel = _(u'Ctrl+Q'),
                                                        helpString = _(u'Quit Chandler'),
                                                        wxId = wx.ID_EXIT))

    menubar = Menu.template('MenuBar',
        setAsMenuBarOnFrame = True,
        childBlocks = [
            fileMenu,
            Menu.template('EditMenu',
                title = _(u'&Edit'),
                childBlocks = [
                    MenuItem.template('UndoItem',
                        event = globalBlocks.Undo,
                        title = messages.UNDO,
                        # L10N: Keyboard shortcut to undo the last operation.
                        accel = _(u'Ctrl+Z'),
                        helpString = _(u"Can't Undo"),
                        wxId = wx.ID_UNDO),
                    MenuItem.template('RedoItem',
                        event = globalBlocks.Redo,
                        title = messages.REDO,
                        # L10N: Keyboard shortcut to redo the last operation.
                        accel = _(u'Ctrl+Y'),
                        helpString = _(u"Can't Redo"),
                        wxId = wx.ID_REDO),
                    MenuItem.template('EditSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('CutItem',
                        event = globalBlocks.Cut,
                        title = messages.CUT,
                        # L10N: Keyboard shortcut for cut.
                        accel = _(u'Ctrl+X'),
                        wxId = wx.ID_CUT),
                    MenuItem.template('CopyItem',
                        event = globalBlocks.Copy,
                        title = messages.COPY,
                        # L10N: Keyboard shortcut for copy.
                        accel = _(u'Ctrl+C'),
                        wxId = wx.ID_COPY),
                    MenuItem.template('PasteItem',
                        event = globalBlocks.Paste,
                        title = messages.PASTE,
                        # L10N: Keyboard shortcut for paste.
                        accel = _(u'Ctrl+V'),
                        wxId = wx.ID_PASTE),
                    MenuItem.template('SelectAllItem',
                        event = globalBlocks.SelectAll,
                        title = messages.SELECT_ALL,
                        # L10N: Keyboard shortcut for select all.
                        accel = _(u'Ctrl+A'),
                        helpString = _(u'Select All'),
                        wxId = wx.ID_SELECTALL),
                    MenuItem.template('EditSeparator2',
                        menuItemKind = 'Separator'),
                    MenuItem.template('SearchItem',
                        event = main.Search,
                        title = _(u'&Find'),
                        # L10N: Keyboard shortcut for find / search.
                        accel = _(u'Ctrl+F'),
                        helpString = _(u'Search'),
                        wxId = wx.ID_FIND),
                    MenuItem.template('SwitchToQuickEntryItem',
                        event = main.SwitchToQuickEntry,
                        title = _(u'Go to Quic&k Entry Field'),
                        # L10N: Keyboard shortcut to put focus on
                        #      the Quick Entry Field.
                        accel = _(u'Ctrl+K'),
                        helpString = _(u'Go to the Quick Entry Field'))
                    ]), # Menu EditMenu
            Menu.template('ViewMenu',
                title = _(u'&View'),
                childBlocks = [
                    MenuItem.template('ApplicationBarAllMenu',
                        event = main.ApplicationBarAll,
                        title = _(u'&All'),
                        menuItemKind = 'Check',
                        helpString = _(u'View all items')),
                    MenuItem.template('ApplicationBarMailMenu',
                        event = main.ApplicationBarMail,
                        title = _(u'&Mail'),
                        menuItemKind = 'Check',
                        helpString = _(u'View messsages')),
                    MenuItem.template('ApplicationBarTaskMenu',
                        event = main.ApplicationBarTask,
                        title = _(u'&Tasks'),
                        menuItemKind = 'Check',
                        helpString = _(u'View tasks')),
                    MenuItem.template('ApplicationBarEventMenu',
                        event = main.ApplicationBarEvent,
                        title = _(u'&Calendar'),
                        menuItemKind = 'Check',
                        helpString = _(u'View events')),
                    MenuItem.template('ViewSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('TriageMenu',
                        event = main.Triage,
                        title = _(u'T&riage'),
                        accel = _(u'F5'),
                        helpString = _(u'Sort items into correct Triage sections')),
                    MenuItem.template('ViewSeparator1.5',
                        menuItemKind = 'Separator'),
                    MenuItem.template('GoToNextWeek',
                        event = calBlocks.GoToNext,
                        title = _(u'&Next Week'),
                        accel = _(u'Alt+Right'),
                        helpString = _(u'Jump to next week')),
                    MenuItem.template('GoToPrevWeek',
                        event = calBlocks.GoToPrev,
                        title = _(u'&Previous Week'),
                        accel = _(u'Alt+Left'),
                        helpString = _(u'Jump to previous week')),
                    MenuItem.template('GoToDate',
                        event = calBlocks.GoToDate,
                        title = _(u'&Go to Date...'),
                        # L10N: Keyboard shortcut to go to a specific date
                        #      on the Calendar.
                        accel = _(u'Ctrl+G'),
                        helpString = _(u'Go to a specific date on the Calendar')),
                    MenuItem.template('GoToToday',
                        event = calBlocks.GoToToday,
                        title = _(u'Go to T&oday'),
                        # L10N: Keyboard shortcut to go to today's date
                        #      on the Calendar.
                        accel = _(u'Ctrl+T'),
                        helpString = _(u'Navigate to today\'s date')),
                    MenuItem.template('ViewSeparator2',
                                      menuItemKind = 'Separator'),
                    Menu.template('VisibleHoursMenu',
                                  title = _(u'&Visible Hours'),
                                  childBlocks = \
                                  makeVisibleHourMenuItems(parcel)),
                    ]), # Menu ViewMenu
            Menu.template('ItemMenu',
                title = _(u'&Item'),
                childBlocks = [
                    Menu.template('NewItemMenu',
                        title = _(u'&New'),
                        helpString = _(u'Create a new item'),
                        childBlocks = [
                            MenuItem.template('NewItemItem',
                                event = main.NewItem,
                                # L10N: One of the possible titles for the  Item -> New -> New Item menu.
                                # This title changes based on the area selected in the Toolbar.
                                # The keyboard mnemonic should be the same for each alternative title.
                                title = _(u'Ne&w Item'),
                                # L10N: Keyboard shortcut to create a new Item.
                                #       The shortcut will either create a Note,
                                #       Task, Event, or Message depending on
                                #       what filter button is selected in the
                                #       Toolbar. The filter buttons are All,
                                #       Mail, Task, Calendar.
                                accel = _(u'Ctrl+N'),
                                helpString = _(u'Create a new item'),
                                wxId = wx.ID_NEW),
                            MenuItem.template('NewItemSeparator1',
                                menuItemKind = 'Separator'),
                            MenuItem.template('NewNoteItem',
                                event = main.NewNote,
                                title = _(u'New &Note'),
                                # L10N: Keyboard shortcut to create a new Note.
                                accel = _(u'Ctrl+Shift+N'),
                                helpString = _(u'Create a new Note')),
                            MenuItem.template('NewMessageItem',
                                event = main.NewMailMessage,
                                title = _(u'New &Message'),
                                # L10N: Keyboard shortcut to create a new Message.
                                accel = _(u'Ctrl+Shift+M'),
                                helpString = _(u'Create a new Message')),
                            MenuItem.template('NewTaskItem',
                                event = main.NewTask,
                                title = _(u'New &Task'),
                                # L10N: Keyboard shortcut to create a new Task.
                                accel = _(u'Ctrl+Shift+T'),
                                helpString = _(u'Create a new Task')),
                            MenuItem.template('NewEventItem',
                                event = main.NewCalendar,
                                title = _(u'New &Event'),
                                # L10N: Keyboard shortcut to create a new Event.
                                accel = _(u'Ctrl+Shift+E'),
                                helpString = _(u'Create a new Event')),
                            ]), # Menu NewItemMenu
                    MenuItem.template('RemoveItem',
                        event = globalBlocks.Remove,
                        title = _(u'Remo&ve'),
                        accel = platform_remove,                        
                        helpString = _(u'Remove the selected item from the selected collection'),
                        wxId = wx.ID_REMOVE),
                    MenuItem.template('DeleteItem',
                        event = globalBlocks.Delete,
                        title = _(u'&Delete'),
                        accel = platform_delete,
                        helpString = _(u'Move the selected item to the Trash'),
                        wxId = wx.ID_DELETE),
                    MenuItem.template('ItemSeparator0',
                        menuItemKind = 'Separator'),
                    MenuItem.template('MarkAsReadItem',
                        event = main.MarkAsRead,
                        title = _(u"&Mark As Read"),
                        helpString = _(u"Mark all selected items as 'Read'")),
                    MenuItem.template('ItemSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('StampMessageItem',
                        event = main.FocusStampMessage,
                        title = _(u"&Address Item"),
                        toggleTitle = _(u"Remove &Addresses"),
                        helpString = messages.STAMP_MAIL_HELP),
                    MenuItem.template('StampTaskItem',
                        event = main.FocusStampTask,
                        title = _(u"Add to &Task list"),
                        toggleTitle = _(u"Remove from &Task list"),
                        helpString = messages.STAMP_TASK_HELP),
                    MenuItem.template('StampEventItem',
                        event = main.FocusStampCalendar,
                        title = _(u"Add to &Calendar"),
                        toggleTitle = _(u"Remove from &Calendar"),
                        helpString = messages.STAMP_CALENDAR_HELP),
                    MenuItem.template('ItemSeparator2',
                        menuItemKind = 'Separator'),
                    MenuItem.template('SendMessageItem',
                        event = main.SendShareItem,
                        title = _(u'&Send'),
                        helpString = _(u'Send the selected message')),
                    MenuItem.template('ReplyMessageItem',
                        event = main.ReplyMessage,
                        title = _(u'&Reply'),
                        helpString = _(u'Reply to the selected message')),
                    MenuItem.template('ReplyAllMessageItem',
                        event = main.ReplyAllMessage,
                        title = _(u'Repl&yAll'),
                        helpString = _(u'Reply to all recipients of the selected message')),
                    MenuItem.template('ForwardMessageItem',
                        event = main.ForwardMessage,
                        title = _(u'For&ward'),
                        helpString = _(u'Forward the selected message')),
                    # Hidden per bug 8999/9000
                    #MenuItem.template('ItemSeparator3',
                        #menuItemKind = 'Separator'),
                    #MenuItem.template('NeverShareItem',
                        #event = main.FocusTogglePrivate,
                        #title = _(u"Never S&hare"),
                        #menuItemKind = 'Check',
                        #helpString = _(u'Mark the selected item as private so it will never be shared')),
                    ]), # Menu ItemMenu
            Menu.template('CollectionMenu',
                title = _(u'&Collection'),
                childBlocks = [
                    MenuItem.template('NewCollectionItem',
                        event = main.NewCollection,
                        eventsForNamedLookup = [main.NewCollection],
                        title = _(u'&New'),
                        helpString = _(u'Create a new collection')),
                    MenuItem.template('CollectionSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('CollectionRenameItem',
                        event = main.RenameCollection,
                        title = _(u'&Rename'),
                        helpString = _(u'Rename the selected collection')),
                    # Bug #8744: Suppress 'duplicate' from collection menu
                    #MenuItem.template('CollectionDuplicateItem',
                    #    event = main.DuplicateSidebarSelection,
                    #    title = _(u'Dup&licate'),
                    #    helpString = _(u'Duplicate the selected collection')),
                    MenuItem.template('CollectionDeleteItem',
                        event = main.DeleteCollection,
                        title = _(u'&Delete'),
                        helpString = _(u'Move the selected collection to the Trash')),
                    MenuItem.template('CollectionEmptyTrashItem',
                        event = main.EmptyTrash,
                        title = _(u'&Empty Trash'),
                        helpString = _(u'Delete all items from the Trash')),
                    MenuItem.template('CollectionSeparator2',
                        menuItemKind = 'Separator'),
                    Menu.template('CollectionColorMenu',
                        title = _(u'&Calendar Color'),
                        childBlocks = makeColorMenuItems(parcel,
                                                            MenuItem,
                                                            usercollections.collectionHues)),
                    MenuItem.template('CollectionSeparator3',
                        menuItemKind = 'Separator'),
                    MenuItem.template('CollectionToggleMineItem',
                        event = main.ToggleMine,
                        title = _(u'&Keep out of Dashboard'),
                        menuItemKind = 'Check',
                        helpString = _(u'Include or exclude the selected collection from the Dashboard')),
                    ]), # Menu CollectionMenu
            Menu.template('ShareMenu',
                title = _(u'&Share'),
                childBlocks = [
                    MenuItem.template('SubscribeToCollectionItem',
                        event = main.SubscribeToCollection,
                        title = _(u'&Subscribe...'),
                        helpString = _(u'Subscribe to a shared collection')),
                    MenuItem.template('UnsubscribeCollectionItem',
                        event = main.UnsubscribeCollection,
                        title = _(u'&Unsubscribe'),
                        helpString = _(u'Stop sharing the selected collection')),
                    MenuItem.template('PublishCollectionItem',
                        event = main.PublishCollection,
                        title = _(u'&Publish...'),
                        helpString = _(u'Publish the selected collection')),
                    MenuItem.template('UnpublishCollectionItem',
                        event = main.UnpublishCollection,
                        title = _(u'U&npublish'),
                        helpString = _(u'Remove the selected shared collection from the server')),
                    MenuItem.template('ManageSidebarCollectionItem',
                        event = main.ManageSidebarCollection,
                        title = _(u'&Manage...'),
                        helpString = _(u'Manage the selected shared collection')),
                    MenuItem.template('ShareSeparator2',
                        menuItemKind = 'Separator'),
                    MenuItem.template('CollectionInviteItem',
                        event = main.CollectionInvite,
                        title = _(u'&Invite...'),
                        helpString = _(u"Open the invitation URLs dialog")),
                    ]), # Menu ShareMenu
            DemoMenu.template('ExperimentalMenu',
                          title = _(u'&Plugins'),
                          childBlocks = [
                    MenuItem.template("BrowsePluginsMenuItem",
                                event = main.BrowsePlugins,
                                title = _(u"&Download"),
                                helpString = _(u'Browse for new plugins')),
                    MenuItem.template('InstallPluginsMenuItem',
                                event = main.InstallPlugins,
                                title = _(u"I&nstall..."),
                                helpString = _(u'Install plugins')),
                    PluginMenu.template('PluginsMenu',
                        title=_(u'&Active'),
                        helpString=_(u'Activate or Deactivate Plugins'),
                        event = main.Plugin,
                        childBlocks = []),
                            ]), # Menu ExperimentalMenu
            Menu.template('ToolsMenu',
                title = _(u'&Tools'),
                childBlocks = [
                    MenuItem.template('ActivateWebserverItem',
                        event = main.ActivateWebserver,
                        title = _(u'Start &Webserver'),
                        helpString = _(u'Activates the built-in webserver at localhost:1888')),
                    Menu.template('LoggingMenu',
                        title=_(u'&Logging'),
                        childBlocks = [
                            MenuItem.template('ShowLogWindowItem',
                                event = main.ShowLogWindow,
                                title = _(u'Log &Window...'),
                                helpString = _(u'Displays the contents of chandler.log')),
                            Menu.template('LoggingLevelMenu',
                                title = _(u'Logging L&evel'),
                                helpString = _(u'Change logging level'),
                                childBlocks = [
                                    MenuItem.template('LoggingLevelCriticalMenuItem',
                                        event = main.SetLoggingLevelCritical,
                                        title = _(u'&Critical'),
                                        menuItemKind = 'Check',
                                        helpString = _(u'Set logging level to Critical')),
                                    MenuItem.template('LoggingLevelErrorMenuItem',
                                        event = main.SetLoggingLevelError,
                                        title = _(u'&Error'),
                                        menuItemKind = 'Check',
                                        helpString = _(u'Set logging level to Error')),
                                    MenuItem.template('LoggingLevelWarningMenuItem',
                                        event = main.SetLoggingLevelWarning,
                                        title = _(u'&Warning'),
                                        menuItemKind = 'Check',
                                        helpString = _(u'Set logging level to Warning')),
                                    MenuItem.template('LoggingLevelInfoMenuItem',
                                        event = main.SetLoggingLevelInfo,
                                        title = _(u'&Info'),
                                        menuItemKind = 'Check',
                                        helpString = _(u'Set logging level to Info')),
                                    MenuItem.template('LoggingLevelDebugMenuItem',
                                        event = main.SetLoggingLevelDebug,
                                        title = _(u'&Debug'),
                                        menuItemKind = 'Check',
                                        helpString = _(u'Set logging level to Debug')),
                                    ]), # Menu LoggingLevelMenu
                            ]), # Menu LoggingMenu
                    Menu.template('SaveRestoreMenu',
                        title = _(u'&Save and Restore'),
                        childBlocks = [
                            MenuItem.template('SaveSettingsItem',
                                event = main.SaveSettings,
                                title = _(u'Sa&ve Settings...'),
                                helpString = _(u'Save settings for your accounts and shared collections')),
                            MenuItem.template('RestoreSettingsItem',
                                event = main.RestoreSettings,
                                title = _(u'Res&tore Settings...'),
                                helpString = _(u'Restore your accounts and shared collections')),
                            MenuItem.template('ToolsRestoreSeparator1',
                                menuItemKind = 'Separator'),
                            MenuItem.template('ObfuscatedDumpToFileItem',
                                event = main.ObfuscatedDumpToFile,
                                title = _(u'&Export Scrubbed Collections and Settings...'),
                                helpString = _(u'Generate export file with obscured data')),
                            MenuItem.template('ToolsRestoreSeparator2',
                                menuItemKind = 'Separator'),
                            MenuItem.template('RestoreSharesItem',
                                event = main.RestoreShares,
                                title = _(u'Restore Published S&hares...'),
                                helpString = _(u'Restore previously published shares')),
                        ]), # Menu SaveRestoreMenu
                    Menu.template('RepositoryTestMenu',
                        title=_(u'&Repository'),
                        helpString=_(u'Repository tools'),
                        childBlocks = [
                            MenuItem.template('CheckRepositoryItem',
                                event = main.CheckRepository,
                                title = _(u'&Check'),
                                helpString = _(u'Run check() on the main view')),
                            MenuItem.template('CheckAndRepairRepositoryItem',
                                event = main.CheckAndRepairRepository,
                                title = _(u'C&heck and Repair'),
                                helpString = _(u'Run check(True) on the main view')),
                            MenuItem.template('CompactRepositoryItem',
                                event = main.CompactRepository,
                                title = _(u'C&ompact'),
                                helpString = _(u'Purge the repository of obsolete data')),
                            MenuItem.template('IndexRepositoryItem',
                                event = main.IndexRepository,
                                title = _(u'&Index'),
                                # L10N: Lucene indexes the Repository
                                helpString = _(u'Tickle the indexer')),
                            MenuItem.template('ToolsRepositorySeparator1',
                                menuItemKind = 'Separator'),
                            MenuItem.template('BackupRepository',
                                event = globalBlocks.BackupRepository,
                                title = _(u'&Back up...')),
                            MenuItem.template('RestoreRepository',
                                event = globalBlocks.RestoreRepository,
                                title = _(u'&Restore...')),
                            MenuItem.template('ToolsRepositorySeparator2',
                                menuItemKind = 'Separator'),
                            MenuItem.template('NewRepositoryItem',
                                event = main.CreateRepository,
                                title = _(u'&New...')),
                            MenuItem.template('SwitchRepositoryItem',
                                event = main.SwitchRepository,
                                title = _(u'&Switch...')),
                        ]), # Menu RepositoryTestMenu
                    Menu.template('ShareTestMenu',
                        title = _(u'S&haring'),
                        helpString = _(u'Sharing-related test commands'),
                        childBlocks = [
                            MenuItem.template('ShowActivityViewerItem',
                                event = main.ShowActivityViewer,
                                title = _(u'Activity &Viewer...'),
                                helpString = _(u'Opens the Activity Viewer')),
                            MenuItem.template("AddSharingLogItem",
                                event = main.AddSharingLogToSidebar,
                                title = _(u"&Add Sharing Activity Log to Sidebar"),
                                helpString = _(u'Add Sharing Activity Log to the Sidebar')),
                            MenuItem.template("ResetShareItem",
                                event = main.ResetShare,
                                title = _(u"Reset State of Shared Collection"),
                                helpString = _(u"Discards metadata about shared items")),
                            MenuItem.template("RecordSetDebuggingItem",
                                event = main.RecordSetDebugging,
                                title = _(u"Set S&haring Logging Level to Debug"),
                                helpString = _(u'Enable RecordSet Debugging')),
                            MenuItem.template("UnsubscribePublishedCollectionItem",
                                event = main.UnsubscribePublishedCollection,
                                title = _(u"&Unsubscribe from Published Shares"),
                                helpString = _(u"Stop syncing to a collection you published without removing it from the server")),
                            ]), # Menu ShareMenu
                    MenuItem.template('ToolsSeparator1',
                                      menuItemKind = 'Separator'),
                    Menu.template('ViewAsCalendarMenu',
                        title = _(u'S&elect View'),
                        helpString = _(u'Select type of main view'),
                        childBlocks = [
                            MenuItem.template('ViewAsDashboardItem',
                                event = main.ViewAsDashboard,
                                title = _(u'Triage Ta&ble View'),
                                menuItemKind = 'Check',
                                helpString = _(u'Go to the Triage Table view')),
                            MenuItem.template('ViewAsCalendarIteminWeekView',
                                event = main.ViewAsWeekCalendar,
                                title = _(u'&Week View'),
                                menuItemKind = 'Check',
                                helpString = _(u'Go to the Calendar Week View')),
                            MenuItem.template('ViewAsCalendarIteminDayView',
                                event = main.ViewAsDayCalendar,
                                title = _(u'&Day View'),
                                menuItemKind = 'Check',
                                helpString = _(u'Go to Calendar Day View'))
                        ]),
                    Menu.template('ViewConfigureWindow',
                        title = _(u'Sh&ow'),
                        helpString = _(u'Show and hide application elements'),
                        childBlocks = [
                            MenuItem.template('ViewToolBarItem',
                                              event = main.ShowHideApplicationBar,
                                              title = _(u'&Toolbar'),
                                              menuItemKind = 'Check',
                                              helpString = _(u'Show or hide the Toolbar')),
                            MenuItem.template('ViewSideBarItem',
                                              event = main.ShowHideSidebar,
                                              title = _(u'&Sidebar'),
                                              menuItemKind = 'Check',
                                              helpString = _(u'Show or hide the Sidebar')),
                            MenuItem.template('ViewMiniCalItem',
                                              title = _(u'&Mini-calendar'),
                                              menuItemKind = 'Check',
                                              helpString = _(u'Show or hide the Mini-calendar')),
                            MenuItem.template('ViewDetailItem',
                                              title = _(u'&Detail View'),
                                              menuItemKind = 'Check',
                                              helpString = _(u'Show or hide the Detail View')),
                            MenuItem.template('ViewStatusBarItem',
                                              event = main.ShowHideStatusBar,
                                              title = _(u'Status &Bar'),
                                              menuItemKind = 'Check',
                                              helpString = _(u'Show or hide the Status Bar')),
                            ]),
                    MenuItem.template('SaveResultsMenuItem',
                        event = main.SaveResults,
                        title = _(u'&Save Search Results'),
                        helpString = _(u'Save a copy of the last search results in the sidebar')),
                    MenuItem.template('ToolsSeparator2',
                                      menuItemKind = 'Separator'),
                ]),
            Menu.template('HelpMenu',
                title = _(u'&Help'),
                childBlocks = [
                    MenuItem.template('AboutChandlerItem',
                        event = globalBlocks.About,
                        title = _(u'&About Chandler'),
                        helpString = _(u'About Chandler...'),
                        wxId = wx.ID_ABOUT),
                     MenuItem.template('GettingStartedMenuItem',
                        event = globalBlocks.GettingStarted,
                        title = _(u'Chandler Get &Started Guide'),
                        helpString =
                             _(u'Open the Chandler Get Started Guide in your web browser')),
                     MenuItem.template('HelpMenuItem',
                        event = globalBlocks.Help,
                        title = _(u'Chandler &FAQ'),
                        helpString =
                             _(u'Open the Chandler FAQ in your web browser'),
                        # L10N: Keyboard shortcut to open the Chandler FAQ in
                        #       a web browser.
                        accel = _(u'Ctrl+?')),
                     MenuItem.template('FileBugMenuItem',
                        event = globalBlocks.FileBug,
                        title = _(u'Report a &Bug'),
                        helpString =
                             _(u'Open instructions on how to file a bug in your web browser')),
                    ]) # Menu HelpMenu
            ]).install (parcel) # Menu MenuBar

    Menu.template('SidebarContextMenu',
                title = _(u'Sidebar'),
                childBlocks = [
                    MenuItem.template('SidebarNewCollectionItem',
                        event = main.NewCollection,
                        title = _(u'&New Collection'),
                        helpString = _(u'Create a new collection')),
                    MenuItem.template('SidebarSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('SidebarRenameItem',
                        event = main.RenameCollection,
                        title = _(u'&Rename'),
                        helpString = _(u'Rename the selected collection')),
                    # Bug #8744: Suppress 'duplicate' from collection menu
                    #MenuItem.template('SidebarDuplicateItem',
                    #    event = main.DuplicateSidebarSelection,
                    #    title = _(u'Dup&licate'),
                    #    helpString = _(u'Duplicate the selected collection')),
                    MenuItem.template('SidebarDeleteItem',
                        event = main.DeleteCollection,
                        title = _(u'&Delete'),
                        helpString = _(u'Move the selected collection to the Trash')),
                    MenuItem.template('SidebarEmptyTrashItem',
                        event = main.EmptyTrash,
                        title = _(u'&Empty Trash'),
                        helpString = _(u'Delete all items from the Trash')),
                    MenuItem.template('SidebarSeparator2',
                        menuItemKind = 'Separator'),
                    Menu.template('SidebarCollectionColorMenu',
                        title = _(u'&Collection Color'),
                        childBlocks = makeColorMenuItems(parcel,
                                                            MenuItem,
                                                            usercollections.collectionHues,
                                                            "Sidebar")),
                    MenuItem.template('SidebarSeparator3',
                        menuItemKind = 'Separator'),
                    MenuItem.template('SidebarToggleMineItem',
                        event = main.ToggleMine,
                        title = _(u'&Keep out of Dashboard'),
                        menuItemKind = 'Check',
                        helpString = _(u'Include or Exclude the selected collection from the Dashboard')),
                    MenuItem.template('SidebarSeparator4',
                        menuItemKind = 'Separator'),
                    MenuItem.template('SidebarSyncCollectionItem',
                        event = main.SyncCollection,
                        title = _(u'S&ync'),
                        helpString = _(u"Sync the selected collection")),
                    MenuItem.template('SidebarTakeOnlineOfflineItem',
                        event = main.TakeOnlineOffline,
                        menuItemKind = 'Check',
                        title = _(u'Suspend Syncin&g'),
                        helpString = _(u"Take the selected collection offline and online")),
                    MenuItem.template('SidebarSyncIMAPItem',
                                event = main.GetNewMail,
                                title = _(u'Sync M&ail'),
                                helpString = _(u'Sync all mail accounts')),
                    MenuItem.template('SidebarSyncWebDAVItem',
                                event = main.SyncWebDAV,
                                title = _(u'Sync S&hares'),
                                helpString = _(u'Sync all shared collections')),
                    MenuItem.template('SidebarSeparator5',
                        menuItemKind = 'Separator'),
                    MenuItem.template('SidebarSubscribeToCollectionItem',
                        event = main.SubscribeToCollection,
                        title = _(u'&Subscribe...'),
                        helpString = _(u'Subscribe to a shared collection')),
                    MenuItem.template('SidebarUnsubscribeCollectionItem',
                        event = main.UnsubscribeCollection,
                        title = _(u'&Unsubscribe'),
                        helpString = _(u'Stop sharing the selected collection')),
                    MenuItem.template('SidebarPublishCollectionItem',
                        event = main.PublishCollection,
                        title = _(u'&Publish...'),
                        helpString = _(u'Publish the selected collection')),
                    MenuItem.template('SidebarUnpublishCollectionItem',
                        event = main.UnpublishCollection,
                        title = _(u'U&npublish'),
                        helpString = _(u'Remove the selected shared collection from the server')),
                    MenuItem.template('SidebarManageSidebarCollectionItem',
                        event = main.ManageSidebarCollection,
                        title = _(u'&Manage...'),
                        helpString = _(u'Manage the selected shared collection')),
                    MenuItem.template('SidebarCollectionInviteItem',
                        event = main.CollectionInvite,
                        title = _(u'&Invite...'),
                        helpString = _(u"Open the invitation URLs dialog")),
                    ]).install(parcel)

    Menu.template('ItemContextMenu',
                title = _(u'Item'),
                childBlocks = [
                    Menu.template('ItemContextNewItemMenu',
                        title = _(u'&New'),
                        helpString = _(u'Create a new item'),
                        childBlocks = [
                            MenuItem.template('ItemContextNewNoteItem',
                                event = main.NewNote,
                                title = _(u'&Note'),
                                # L10N: Keyboard shortcut to create a new Note.
                                accel = _(u'Ctrl+Shift+N'),
                                helpString = _(u'Create a new note')),
                            MenuItem.template('ItemContextNewMessageItem',
                                event = main.NewMailMessage,
                                title = _(u'&Message'),
                                # L10N: Keyboard shortcut to create a new Message.
                                accel = _(u'Ctrl+Shift+M'),
                                helpString = _(u'Create a new message')),
                            MenuItem.template('ItemContextNewTaskItem',
                                event = main.NewTask,
                                title = _(u'&Task'),
                                # L10N: Keyboard shortcut to create a new Task.
                                accel = _(u'Ctrl+Shift+T'),
                                helpString = _(u'Create a new task')),
                            MenuItem.template('ItemContextNewEventItem',
                                event = main.NewCalendar,
                                title = _(u'&Event'),
                                # L10N: Keyboard shortcut to create a new Event.
                                accel = _(u'Ctrl+Shift+E'),
                                helpString = _(u'Create a new event')),
                            ]),
                    MenuItem.template('ItemContextCutItem',
                        event = main.CutInActiveView,
                        title = messages.CUT),
                    MenuItem.template('ItemContextCopyItem',
                        event = main.CopyInActiveView,
                        title = messages.COPY),
                    MenuItem.template('ItemContextDuplicateItem',
                        event = main.DuplicateInActiveView,
                        title = _(u'Dup&licate'),
                        helpString = _(u'Duplicate the selected item')),
                    MenuItem.template('ItemContextPasteItem',
                        event = main.PasteInActiveView,
                        title = messages.PASTE),
                    MenuItem.template('ItemContextRemoveItem',
                        event = main.RemoveInActiveView,
                        title = _(u'Remo&ve'),
                        accel = platform_remove,
                        helpString = _(u'Remove the selected items from the selected collection')),                    
                    MenuItem.template('ItemContextDeleteItem',
                        event = main.DeleteInActiveView,
                        title = _(u'&Delete'),
                        accel = platform_delete,                        
                        helpString = _(u'Move the selected item to the Trash')),
                    MenuItem.template('ItemContextSeparator0',
                        menuItemKind = 'Separator'),
                    MenuItem.template('ItemContextMarkAsReadItem',
                        event = main.MarkAsRead,
                        title = _(u"&Mark As Read"),
                        helpString = _(u"Mark all selected items as 'Read'")),
                    MenuItem.template('ItemContextSeparator1',
                        menuItemKind = 'Separator'),
                    MenuItem.template('ItemContextStampMessageItem',
                        event = main.FocusStampMessage,
                        title = _(u"&Address Item"),
                        toggleTitle = _(u"Remove &Addresses"),
                        helpString = messages.STAMP_MAIL_HELP),
                    MenuItem.template('ItemContextStampTaskItem',
                        event = main.FocusStampTask,
                        title = _(u"Add to &Task list"),
                        toggleTitle = _(u"Remove from &Task list"),
                        helpString = messages.STAMP_TASK_HELP),
                    MenuItem.template('ItemContextStampEventItem',
                        event = main.FocusStampCalendar,
                        title = _(u"Add to &Calendar"),
                        toggleTitle = _(u"Remove from &Calendar"),
                        helpString = messages.STAMP_CALENDAR_HELP),
                    MenuItem.template('ItemContextSeparator2',
                        menuItemKind = 'Separator'),
                    MenuItem.template('ItemContextSendMessageItem',
                        event = main.SendShareItem,
                        title = _(u'&Send'),
                        helpString = _(u'Send the selected message')),
                    MenuItem.template('ItemContextReplyMessageItem',
                        event = main.ReplyMessage,
                        title = _(u'&Reply'),
                        helpString = _(u'Reply to the selected message')),
                    MenuItem.template('ItemContextReplyAllMessageItem',
                        event = main.ReplyAllMessage,
                        title = _(u'Repl&yAll'),
                        helpString = _(u'Reply to all recipients of the selected message')),
                    MenuItem.template('ItemContextForwardMessageItem',
                        event = main.ForwardMessage,
                        title = _(u'For&ward'),
                        helpString = _(u'Forward the selected message')),
                    # Hidden per bug 8999/9000
                    #MenuItem.template('ItemContextSeparator3',
                        #menuItemKind = 'Separator'),
                    #MenuItem.template('ItemContextNeverShareItem',
                        #event = main.FocusTogglePrivate,
                        #title = _(u"Never S&hare"),
                        #menuItemKind = 'Check',
                        #helpString = _(u'Mark the selected item as private so it will never be shared')),
                    ]).install(parcel)

    return menubar
