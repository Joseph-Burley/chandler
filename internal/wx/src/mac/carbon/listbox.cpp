///////////////////////////////////////////////////////////////////////////////
// Name:        src/mac/carbon/listbox.cpp
// Purpose:     wxListBox
// Author:      Stefan Csomor
// Modified by:
// Created:     1998-01-01
// RCS-ID:      $Id: listbox.cpp,v 1.108 2006/03/09 13:08:07 VZ Exp $
// Copyright:   (c) Stefan Csomor
// Licence:     wxWindows licence
///////////////////////////////////////////////////////////////////////////////

#include "wx/wxprec.h"

#if wxUSE_LISTBOX

#include "wx/app.h"
#include "wx/listbox.h"
#include "wx/button.h"
#include "wx/settings.h"
#include "wx/toplevel.h"
#include "wx/dynarray.h"
#include "wx/log.h"

#include "wx/utils.h"

#include "wx/mac/uma.h"

const short kTextColumnId = 1024 ;

// new DataBrowser-based version:
// because of the limited insert functionality of DataBrowser,
// we just introduce IDs corresponding to the line number


IMPLEMENT_DYNAMIC_CLASS(wxListBox, wxControl)

BEGIN_EVENT_TABLE(wxListBox, wxControl)
#ifndef __WXMAC_OSX__
//    EVT_SIZE( wxListBox::OnSize )
    EVT_CHAR( wxListBox::OnChar )
#endif
END_EVENT_TABLE()


DataBrowserItemDataUPP gDataBrowserItemDataUPP = NULL ;
DataBrowserItemNotificationUPP gDataBrowserItemNotificationUPP = NULL ;
DataBrowserDrawItemUPP gDataBrowserDrawItemUPP = NULL ;


#if TARGET_API_MAC_OSX
static pascal void DataBrowserItemNotificationProc(ControlRef browser, DataBrowserItemID itemID,
    DataBrowserItemNotification message, DataBrowserItemDataRef itemData)
#else
static pascal void DataBrowserItemNotificationProc(ControlRef browser, DataBrowserItemID itemID,
    DataBrowserItemNotification message)
#endif
{
    long ref = GetControlReference( browser ) ;
    if ( ref )
    {
        wxListBox* list = wxDynamicCast( (wxObject*) ref , wxListBox ) ;
        int i = itemID - 1 ;
        if (i >= 0 && i < list->GetCount() )
        {
            bool trigger = false ;
            wxCommandEvent event( wxEVT_COMMAND_LISTBOX_SELECTED, list->GetId() );
            switch ( message )
            {
                case kDataBrowserItemDeselected :
                    if ( list->HasMultipleSelection() )
                        trigger = !list->MacIsSelectionSuppressed() ;
                    break ;

                case kDataBrowserItemSelected :
                    trigger = !list->MacIsSelectionSuppressed() ;
                    break ;

                case kDataBrowserItemDoubleClicked :
                    event.SetEventType( wxEVT_COMMAND_LISTBOX_DOUBLECLICKED ) ;
                    trigger = true ;
                    break ;

                default :
                    break ;
            }

            if ( trigger )
            {
                event.SetEventObject( list );
                if ( list->HasClientObjectData() )
                    event.SetClientObject( list->GetClientObject( i ) );
                else if ( list->HasClientUntypedData() )
                    event.SetClientData( list->GetClientData( i ) );
                event.SetString( list->GetString( i ) );
                event.SetInt( i ) ;
                event.SetExtraLong( list->HasMultipleSelection() ? message == kDataBrowserItemSelected : true );
                wxPostEvent( list->GetEventHandler() , event ) ;
                // direct notification is not always having the listbox GetSelection() having in synch with event
                // list->GetEventHandler()->ProcessEvent(event) ;
            }
        }
    }
}

static pascal OSStatus ListBoxGetSetItemData(ControlRef browser,
    DataBrowserItemID itemID, DataBrowserPropertyID property,
    DataBrowserItemDataRef itemData, Boolean changeValue)
{
    OSStatus err = errDataBrowserPropertyNotSupported;

    if ( ! changeValue )
    {
        switch (property)
        {
            case kTextColumnId:
            {
                long ref = GetControlReference( browser ) ;
                if ( ref )
                {
                    wxListBox* list = wxDynamicCast( (wxObject*) ref , wxListBox ) ;
                    int i = itemID - 1 ;
                    if (i >= 0 && i < list->GetCount() )
                    {
                        wxMacCFStringHolder cf( list->GetString( i ) , list->GetFont().GetEncoding() ) ;
                        verify_noerr( ::SetDataBrowserItemDataText( itemData , cf ) ) ;
                        err = noErr ;
                    }
                }
            }
                break;

            default:
                break;
        }
    }

    return err;
}

static pascal void ListBoxDrawProc( ControlRef browser , DataBrowserItemID item , DataBrowserPropertyID property ,
    DataBrowserItemState itemState , const Rect *itemRect , SInt16 depth , Boolean isColorDevice )
{
    CFStringRef      cfString;
    ThemeDrawingState themeState ;
    long        systemVersion;

    GetThemeDrawingState( &themeState ) ;
    cfString = CFStringCreateWithFormat( NULL, NULL, CFSTR("Row %d"), item );

    //  In this sample we handle the "selected" state; all others fall through to our "active" state
    if ( itemState == kDataBrowserItemIsSelected )
    {
        ThemeBrush colorBrushID;

        Gestalt( gestaltSystemVersion, &systemVersion );

        // TODO: switch over to wxSystemSettingsNative::GetColour() when kThemeBrushSecondaryHighlightColor is incorporated
        // Panther DB starts using kThemeBrushSecondaryHighlightColor for inactive browser hilighting
        if ( (systemVersion >= 0x00001030) && !IsControlActive( browser ) )
            colorBrushID = kThemeBrushSecondaryHighlightColor;
        else
            colorBrushID = kThemeBrushPrimaryHighlightColor;

        // First paint the hilite rect, then the text on top
        SetThemePen( colorBrushID, 32, true );
        PaintRect( itemRect );
        SetThemeDrawingState( themeState , false ) ;
    }

    DrawThemeTextBox( cfString, kThemeApplicationFont, kThemeStateActive, true, itemRect, teFlushDefault, NULL );
    SetThemeDrawingState( themeState , true ) ;

    if ( cfString != NULL )
        CFRelease( cfString );
}

// Listbox item
wxListBox::wxListBox()
{
    m_noItems = 0;
    m_selected = 0;
    m_macList = NULL ;
    m_suppressSelection = false ;
}

bool wxListBox::Create(wxWindow *parent,
    wxWindowID id,
    const wxPoint& pos,
    const wxSize& size,
    const wxArrayString& choices,
    long style,
    const wxValidator& validator,
    const wxString& name)
{
    wxCArrayString chs(choices);

    return Create(parent, id, pos, size, chs.GetCount(), chs.GetStrings(),
                  style, validator, name);
}

bool wxListBox::Create(wxWindow *parent,
    wxWindowID id,
    const wxPoint& pos,
    const wxSize& size,
    int n,
    const wxString choices[],
    long style,
    const wxValidator& validator,
    const wxString& name)
{
    m_macIsUserPane = false ;

    wxASSERT_MSG( !(style & wxLB_MULTIPLE) || !(style & wxLB_EXTENDED),
                  _T("only one of listbox selection modes can be specified") );

    if ( !wxListBoxBase::Create(parent, id, pos, size, style & ~(wxHSCROLL|wxVSCROLL), validator, name) )
        return false;

    m_noItems = 0 ; // this will be increased by our append command
    m_selected = 0;

    Rect bounds = wxMacGetBoundsForControl( this , pos , size ) ;

    m_peer = new wxMacControl( this ) ;
    verify_noerr(
        ::CreateDataBrowserControl(
            MAC_WXHWND(parent->MacGetTopLevelWindowRef()), &bounds,
            kDataBrowserListView, m_peer->GetControlRefAddr() ) );

    DataBrowserSelectionFlags  options = kDataBrowserDragSelect ;
    if ( style & wxLB_MULTIPLE )
        options |= kDataBrowserAlwaysExtendSelection | kDataBrowserCmdTogglesSelection  ;
    else if ( style & wxLB_EXTENDED )
        ; // default behaviour
    else
        options |= kDataBrowserSelectOnlyOne ;

    verify_noerr( m_peer->SetSelectionFlags( options ) );

    if ( gDataBrowserItemDataUPP == NULL )
        gDataBrowserItemDataUPP = NewDataBrowserItemDataUPP(ListBoxGetSetItemData) ;
    if ( gDataBrowserItemNotificationUPP == NULL )
    {
        gDataBrowserItemNotificationUPP =
#if TARGET_API_MAC_OSX
            (DataBrowserItemNotificationUPP) NewDataBrowserItemNotificationWithItemUPP(DataBrowserItemNotificationProc) ;
#else
            NewDataBrowserItemNotificationUPP(DataBrowserItemNotificationProc) ;
#endif
    }

    if ( gDataBrowserDrawItemUPP == NULL )
        gDataBrowserDrawItemUPP = NewDataBrowserDrawItemUPP(ListBoxDrawProc) ;

    DataBrowserCallbacks callbacks ;
    InitializeDataBrowserCallbacks( &callbacks , kDataBrowserLatestCallbacks ) ;

    callbacks.u.v1.itemDataCallback = gDataBrowserItemDataUPP;
    callbacks.u.v1.itemNotificationCallback = gDataBrowserItemNotificationUPP;
    m_peer->SetCallbacks( &callbacks);

    DataBrowserCustomCallbacks customCallbacks ;
    InitializeDataBrowserCustomCallbacks( &customCallbacks , kDataBrowserLatestCustomCallbacks ) ;

    customCallbacks.u.v1.drawItemCallback = gDataBrowserDrawItemUPP ;

    SetDataBrowserCustomCallbacks( m_peer->GetControlRef() , &customCallbacks ) ;

    DataBrowserListViewColumnDesc columnDesc ;
    columnDesc.headerBtnDesc.titleOffset = 0;
    columnDesc.headerBtnDesc.version = kDataBrowserListViewLatestHeaderDesc;
    columnDesc.headerBtnDesc.btnFontStyle.flags = kControlUseFontMask | kControlUseJustMask;
    columnDesc.headerBtnDesc.btnContentInfo.contentType = kControlNoContent;
    columnDesc.headerBtnDesc.btnFontStyle.just = teFlushDefault;
    columnDesc.headerBtnDesc.minimumWidth = 0;
    columnDesc.headerBtnDesc.maximumWidth = 10000;

    columnDesc.headerBtnDesc.btnFontStyle.font = kControlFontViewSystemFont;
    columnDesc.headerBtnDesc.btnFontStyle.style = normal;
    columnDesc.headerBtnDesc.titleString = NULL ; // CFSTR( "" );

    columnDesc.propertyDesc.propertyID = kTextColumnId;
    columnDesc.propertyDesc.propertyType = kDataBrowserTextType ; // kDataBrowserCustomType;
    columnDesc.propertyDesc.propertyFlags = kDataBrowserTableViewSelectionColumn;

#if MAC_OS_X_VERSION_MAX_ALLOWED > MAC_OS_X_VERSION_10_2
    columnDesc.propertyDesc.propertyFlags |= kDataBrowserListViewTypeSelectColumn;
#endif

    verify_noerr( m_peer->AddListViewColumn( &columnDesc, kDataBrowserListViewAppendColumn ) ) ;
    verify_noerr( m_peer->AutoSizeListViewColumns() ) ;
    verify_noerr( m_peer->SetHasScrollBars( false, true ) ) ;
    verify_noerr( m_peer->SetTableViewHiliteStyle( kDataBrowserTableViewFillHilite ) ) ;
    verify_noerr( m_peer->SetListViewHeaderBtnHeight( 0 ) ) ;

#if 0
    // shouldn't be necessary anymore under 10.2
    m_peer->SetData( kControlNoPart, kControlDataBrowserIncludesFrameAndFocusTag, (Boolean) false ) ;
    m_peer->SetNeedsFocusRect( true ) ;
#endif

    MacPostControlCreate( pos, size ) ;

    for ( int i = 0 ; i < n ; i++ )
    {
        Append( choices[i] ) ;
    }

    // Needed because it is a wxControlWithItems
    SetBestSize(size);

    return true;
}

wxListBox::~wxListBox()
{
    m_peer->SetReference( 0 ) ;
    FreeData() ;

    // avoid access during destruction
    if ( m_macList )
        m_macList = NULL ;
}

void wxListBox::FreeData()
{
    if ( HasClientObjectData() )
    {
        for ( size_t n = 0; n < (size_t)m_noItems; n++ )
        {
            delete GetClientObject( n );
        }
    }
}

void  wxListBox::DoSetSize(int x, int y,
            int width, int height,
            int sizeFlags )
{
    wxControl::DoSetSize( x , y , width , height , sizeFlags ) ;
}

void wxListBox::DoSetFirstItem(int n)
{
    MacScrollTo( n ) ;
}

void wxListBox::Delete(int n)
{
    wxCHECK_RET( n >= 0 && n < m_noItems,
                 wxT("invalid index in wxListBox::Delete") );

    if ( HasClientObjectData() )
        delete GetClientObject( n );

    m_stringArray.RemoveAt( n ) ;
    m_dataArray.RemoveAt( n ) ;
    m_noItems--;

    MacDelete( n ) ;
}

int wxListBox::DoAppend(const wxString& item)
{
    InvalidateBestSize();

    int index = m_noItems ;
    m_stringArray.Add( item ) ;
    m_dataArray.Add( NULL );
    m_noItems++;
    DoSetItemClientData( index , NULL ) ;
    MacAppend( item ) ;

    return index ;
}

void wxListBox::DoSetItems(const wxArrayString& choices, void** clientData)
{
    Clear() ;
    int n = choices.GetCount();

    for ( int i = 0 ; i < n ; ++i )
    {
        if ( clientData )
            Append( choices[i] , clientData[i] ) ;
        else
            Append( choices[i] ) ;
    }
}

int wxListBox::FindString(const wxString& s, bool bCase) const
{
    if ( s.Right(1) == wxT("*") )
    {
        wxString search = s.Left( s.Length() - 1 ) ;
        int len = search.Length() ;
        Str255 s1 , s2 ;
        wxMacStringToPascal( search , s2 ) ;

        for ( int i = 0 ; i < m_noItems ; ++ i )
        {
            wxMacStringToPascal( m_stringArray[i].Left( len ) , s1 ) ;

            if ( EqualString( s1 , s2 , bCase , false ) )
                return i ;
        }

        if ( s.Left(1) == wxT("*") && s.Length() > 1 )
        {
            wxString st = s ;
            st.MakeLower() ;

            for ( int i = 0 ; i < m_noItems ; ++i )
            {
                if ( GetString( i ).Lower().Matches(st) )
                    return i ;
            }
        }
    }
    else
    {
        Str255 s1 , s2 ;

        wxMacStringToPascal( s , s2 ) ;

        for ( int i = 0 ; i < m_noItems ; ++ i )
        {
            wxMacStringToPascal( m_stringArray[i] , s1 ) ;

            if ( EqualString( s1 , s2 , bCase , false ) )
                return i ;
        }
    }

    return wxNOT_FOUND;
}

void wxListBox::Clear()
{
    FreeData();
    m_noItems = 0;
    m_stringArray.Empty() ;
    m_dataArray.Empty() ;
    MacClear() ;
}

void wxListBox::DoSetSelection(int n, bool select)
{
    wxCHECK_RET( n == wxNOT_FOUND || (n >= 0 && n < m_noItems) ,
        wxT("invalid index in wxListBox::SetSelection") );

    if ( n == wxNOT_FOUND )
        MacDeselectAll() ;
    else
        MacSetSelection( n , select ) ;
}

bool wxListBox::IsSelected(int n) const
{
    wxCHECK_MSG( n >= 0 && n < m_noItems, false,
        wxT("invalid index in wxListBox::Selected") );

    return MacIsSelected( n ) ;
}

void *wxListBox::DoGetItemClientData(int n) const
{
    wxCHECK_MSG( n >= 0 && n < m_noItems, NULL,
        wxT("invalid index in wxListBox::GetClientData"));

    return (void *)m_dataArray[n];
}

wxClientData *wxListBox::DoGetItemClientObject(int n) const
{
    return (wxClientData *) DoGetItemClientData( n ) ;
}

void wxListBox::DoSetItemClientData(int n, void *clientData)
{
    wxCHECK_RET( n >= 0 && n < m_noItems,
        wxT("invalid index in wxListBox::SetClientData") );

    wxASSERT_MSG( m_dataArray.GetCount() >= (size_t) n , wxT("invalid client_data array") ) ;

    if ( m_dataArray.GetCount() > (size_t) n )
        m_dataArray[n] = (char*)clientData ;
    else
        m_dataArray.Add( (char*)clientData ) ;
}

void wxListBox::DoSetItemClientObject(int n, wxClientData* clientData)
{
    DoSetItemClientData(n, clientData);
}

// Return number of selections and an array of selected integers
int wxListBox::GetSelections(wxArrayInt& aSelections) const
{
    return MacGetSelections( aSelections ) ;
}

// Get single selection, for single choice list items
int wxListBox::GetSelection() const
{
    return MacGetSelection() ;
}

// Find string for position
wxString wxListBox::GetString(int n) const
{
    wxCHECK_MSG( n >= 0 && n < m_noItems, wxEmptyString,
                 wxT("invalid index in wxListBox::GetString") );

    return m_stringArray[n]  ;
}

void wxListBox::DoInsertItems(const wxArrayString& items, int pos)
{
    wxCHECK_RET( pos >= 0 && pos <= m_noItems,
        wxT("invalid index in wxListBox::InsertItems") );

    InvalidateBestSize();

    int nItems = items.GetCount();

    for ( int i = 0 ; i < nItems ; i++ )
    {
        m_stringArray.Insert( items[i] , pos + i ) ;
        m_dataArray.Insert( NULL , pos + i ) ;
        m_noItems++ ;
        MacInsert( pos + i , items[i] ) ;
    }
}

void wxListBox::SetString(int n, const wxString& s)
{
    m_stringArray[n] = s ;
    MacSet( n , s ) ;
}

wxSize wxListBox::DoGetBestSize() const
{
    int lbWidth = 100;  // some defaults
    int lbHeight = 110;
    int wLine;

    {
        wxMacPortStateHelper st( UMAGetWindowPort( (WindowRef)MacGetTopLevelWindowRef() ) ) ;

        // TODO: clean this up
        if ( m_font.Ok() )
        {
            ::TextFont( m_font.MacGetFontNum() ) ;
            ::TextSize( m_font.MacGetFontSize() ) ;
            ::TextFace( m_font.MacGetFontStyle() ) ;
        }
        else
        {
            ::TextFont( kFontIDMonaco ) ;
            ::TextSize( 9  );
            ::TextFace( 0 ) ;
        }

        // Find the widest line
        for (int i = 0; i < GetCount(); i++)
        {
            wxString str( GetString( i ) );

#if wxUSE_UNICODE
            Point bounds = {0, 0} ;
            SInt16 baseline ;

            // NB: what if m_font.Ok() == false ???
            ::GetThemeTextDimensions(
                wxMacCFStringHolder( str , m_font.GetEncoding() ) ,
                kThemeCurrentPortFont,
                kThemeStateActive,
                false,
                &bounds,
                &baseline );
            wLine = bounds.h ;
#else
            wLine = ::TextWidth( str.c_str() , 0 , str.Length() ) ;
#endif

            lbWidth = wxMax( lbWidth, wLine );
        }

        // Add room for the scrollbar
        lbWidth += wxSystemSettings::GetMetric(wxSYS_VSCROLL_X);

        // And just a bit more
        int cy = 12 ;
        int cx = ::TextWidth( "X" , 0 , 1 ) ;
        lbWidth += cx ;

        // don't make the listbox too tall (limit height to around 10 items)
        // but don't make it too small neither
        lbHeight = wxMax( (cy + 4) * wxMin( wxMax( GetCount(), 3 ), 10 ), 70 );
    }

    return wxSize( lbWidth, lbHeight );
}

int wxListBox::GetCount() const
{
    return m_noItems;
}

void wxListBox::Refresh(bool eraseBack, const wxRect *rect)
{
    wxControl::Refresh( eraseBack , rect ) ;
}

// Some custom controls depend on this
/* static */ wxVisualAttributes
wxListBox::GetClassDefaultAttributes(wxWindowVariant WXUNUSED(variant))
{
    wxVisualAttributes attr;

    attr.colFg = wxSystemSettings::GetColour( wxSYS_COLOUR_WINDOWTEXT );
    attr.colBg = wxSystemSettings::GetColour( wxSYS_COLOUR_LISTBOX );
    attr.font = wxSystemSettings::GetFont( wxSYS_DEFAULT_GUI_FONT );

    return attr;
}

// ============================================================================
// list box control implementation
// ============================================================================

void wxListBox::MacDelete( int n )
{
    wxArrayInt selectionBefore ;
    MacGetSelections( selectionBefore ) ;

    UInt32 id = m_noItems + 1 ;

    verify_noerr( m_peer->RemoveItems( kDataBrowserNoItem , 1 , (UInt32*) &id , kDataBrowserItemNoProperty ) ) ;
    for ( size_t i = 0 ; i < selectionBefore.GetCount() ; ++i )
    {
        int current = selectionBefore[i] ;
        if ( current == n )
        {
            // selection was deleted
            MacSetSelection( current , false ) ;
        }
        else if ( current > n )
        {
            // something behind the deleted item was selected -> move up
            MacSetSelection( current - 1 , true ) ;
            MacSetSelection( current , false ) ;
        }
    }

    // refresh all
    verify_noerr(
        m_peer->UpdateItems(
            kDataBrowserNoItem, 1, (UInt32*)kDataBrowserNoItem,
            kDataBrowserItemNoProperty, kDataBrowserItemNoProperty ) ) ;
}

void wxListBox::MacInsert( int n , const wxString& text )
{
    wxArrayInt selectionBefore ;
    MacGetSelections( selectionBefore ) ;

    // this has already been increased
    UInt32 id = m_noItems ;
    verify_noerr( m_peer->AddItems( kDataBrowserNoItem , 1 , (UInt32*) &id , kDataBrowserItemNoProperty ) ) ;

    for ( int i = selectionBefore.GetCount()-1 ; i >= 0 ; --i )
    {
        int current = selectionBefore[i] ;
        if ( current >= n )
        {
            MacSetSelection( current + 1 , true ) ;
            MacSetSelection( current , false ) ;
        }
    }

    // refresh all
    verify_noerr(
        m_peer->UpdateItems(
            kDataBrowserNoItem, 1, (UInt32*)kDataBrowserNoItem,
            kDataBrowserItemNoProperty, kDataBrowserItemNoProperty ) ) ;
}

void wxListBox::MacAppend( const wxString& text )
{
    UInt32 id = m_noItems ; // this has already been increased
    verify_noerr( m_peer->AddItems( kDataBrowserNoItem , 1 , (UInt32*) &id , kDataBrowserItemNoProperty ) ) ;
    // no need to deal with selections nor refreshed, as we have appended
}

void wxListBox::MacClear()
{
    verify_noerr( m_peer->RemoveItems( kDataBrowserNoItem , 0 , NULL , kDataBrowserItemNoProperty ) ) ;
}

void wxListBox::MacDeselectAll()
{
    bool former = MacSuppressSelection( true ) ;
    verify_noerr(m_peer->SetSelectedItems( 0 , NULL , kDataBrowserItemsRemove ) ) ;
    MacSuppressSelection( former ) ;
}

void wxListBox::MacSetSelection( int n , bool select )
{
    bool former = MacSuppressSelection( true ) ;
    UInt32 id = n + 1 ;

    if ( m_peer->IsItemSelected( id ) != select )
    {
        if ( select )
            verify_noerr( m_peer->SetSelectedItems( 1 , & id , HasMultipleSelection() ? kDataBrowserItemsAdd : kDataBrowserItemsAssign ) ) ;
        else
            verify_noerr( m_peer->SetSelectedItems( 1 , & id , kDataBrowserItemsRemove ) ) ;
    }

    MacScrollTo( n ) ;
    MacSuppressSelection( former ) ;
}

bool wxListBox::MacSuppressSelection( bool suppress )
{
    bool former = m_suppressSelection ;
    m_suppressSelection = suppress ;
    return former ;
}

bool wxListBox::MacIsSelected( int n ) const
{
    return m_peer->IsItemSelected( n + 1 ) ;
}

int wxListBox::MacGetSelection() const
{
    for ( int i = 0 ; i < GetCount() ; ++i )
    {
        if ( m_peer->IsItemSelected( i + 1 ) )
            return i ;
    }

    return -1 ;
}

int wxListBox::MacGetSelections( wxArrayInt& aSelections ) const
{
    int no_sel = 0 ;

    aSelections.Empty();

    UInt32 first , last ;
    m_peer->GetSelectionAnchor( &first , &last ) ;
    if ( first != kDataBrowserNoItem )
    {
        for ( size_t i = first ; i <= last ; ++i )
        {
            if ( m_peer->IsItemSelected( i ) )
            {
                aSelections.Add( i - 1 ) ;
                no_sel++ ;
            }
        }
    }

    return no_sel ;
}

void wxListBox::MacSet( int n , const wxString& text )
{
    // as we don't store the strings we only have to issue a redraw
    UInt32 id = n + 1 ;
    verify_noerr( m_peer->UpdateItems( kDataBrowserNoItem , 1 , &id , kDataBrowserItemNoProperty , kDataBrowserItemNoProperty ) ) ;
}

void wxListBox::MacScrollTo( int n )
{
    UInt32 id = n + 1 ;
    verify_noerr( m_peer->RevealItem( id , kTextColumnId , kDataBrowserRevealWithoutSelecting ) ) ;
}

int wxListBox::DoListHitTest(const wxPoint& point) const
{
    //Yuck - there is no easy way to get a databrowseritem from a point
    //so we need to iterate through our items to see which one this falls under

    // TODO: binary search would be faster
    int count = GetCount();
    DataBrowserTableViewColumnID colId = 0;

    //Get column property id (req. for call to itempartbounds)
    GetDataBrowserTableViewColumnProperty(m_peer->GetControlRef(), 0, &colId);
    
    for(int i = 1; i <= count; ++i)
    {
        Rect bounds;
        GetDataBrowserItemPartBounds(m_peer->GetControlRef(), i, colId, 
                                     kDataBrowserPropertyEnclosingPart,
                                     &bounds);
        
        //translate to client coords
        //
        // TODO: it would probably be more efficient to translate point to
        //       screen coordinates once outside of the loop
        MacRootWindowToWindow(&bounds.left, &bounds.top);
        MacRootWindowToWindow(&bounds.right, &bounds.bottom);
        
        //if point is within the bounds, return this item
        if( (point.x >= bounds.left && point.x <= bounds.right) &&
            (point.y >= bounds.top && point.y <= bounds.bottom) )
        {
            return i - 1; //found
        }
    }
    
    return wxNOT_FOUND;
}

#if !TARGET_API_MAC_OSX

void wxListBox::OnChar(wxKeyEvent& event)
{
    // TODO: trigger proper events here
    event.Skip() ;
    return ;

    if ( event.GetKeyCode() == WXK_RETURN || event.GetKeyCode() == WXK_NUMPAD_ENTER)
    {
        wxWindow* parent = GetParent() ;

        while ( parent  && !parent->IsTopLevel() && parent->GetDefaultItem() == NULL )
            parent = parent->GetParent() ;

        if ( parent && parent->GetDefaultItem() )
        {
            wxButton *def = wxDynamicCast(parent->GetDefaultItem(), wxButton);
            if ( def && def->IsEnabled() )
            {
                wxCommandEvent event( wxEVT_COMMAND_BUTTON_CLICKED, def->GetId() );
                event.SetEventObject( def );
                def->Command( event );

                return ;
            }
        }

        event.Skip() ;
    }

    /* generate wxID_CANCEL if command-. or <esc> has been pressed (typically in dialogs) */
    else if (event.GetKeyCode() == WXK_ESCAPE || (event.GetKeyCode() == '.' && event.MetaDown() ) )
    {
        // FIXME: look in ancestors, not just parent.
        wxWindow* win = GetParent()->FindWindow( wxID_CANCEL ) ;
        if (win)
        {
            wxCommandEvent new_event(wxEVT_COMMAND_BUTTON_CLICKED,wxID_CANCEL);
            new_event.SetEventObject( win );
            win->GetEventHandler()->ProcessEvent( new_event );
          }
    }
    else if ( event.GetKeyCode() == WXK_TAB )
    {
        wxNavigationKeyEvent new_event;
        new_event.SetEventObject( this );
        new_event.SetDirection( !event.ShiftDown() );
        /* CTRL-TAB changes the (parent) window, i.e. switch notebook page */
        new_event.SetWindowChange( event.ControlDown() );
        new_event.SetCurrentFocus( this );
        if ( !GetEventHandler()->ProcessEvent( new_event ) )
            event.Skip() ;
    }
    else if ( event.GetKeyCode() == WXK_DOWN || event.GetKeyCode() == WXK_UP )
    {
        // perform the default key handling first
        wxControl::OnKeyDown( event ) ;

        wxCommandEvent event( wxEVT_COMMAND_LISTBOX_SELECTED, m_windowId );
        event.SetEventObject( this );

        wxArrayInt aSelections;
        int n, count = GetSelections(aSelections);
        if ( count > 0 )
        {
            n = aSelections[0];
            if ( HasClientObjectData() )
                event.SetClientObject( GetClientObject( n ) );
            else if ( HasClientUntypedData() )
                event.SetClientData( GetClientData( n ) );
            event.SetString( GetString( n ) );
        }
        else
        {
            n = -1;
        }

        event.SetInt( n );

        GetEventHandler()->ProcessEvent(event);
    }
    else
    {
        if ( event.GetTimestamp() > m_lastTypeIn + 60 )
            m_typeIn = wxEmptyString ;

        m_lastTypeIn = event.GetTimestamp() ;
        m_typeIn += (char) event.GetKeyCode() ;
        int line = FindString( wxT("*") + m_typeIn + wxT("*") ) ;
        if ( line >= 0 )
        {
            if ( GetSelection() != line )
            {
                SetSelection( line ) ;

                wxCommandEvent event( wxEVT_COMMAND_LISTBOX_SELECTED, m_windowId );
                event.SetEventObject( this );

                if ( HasClientObjectData() )
                    event.SetClientObject( GetClientObject( line ) );
                else if ( HasClientUntypedData() )
                    event.SetClientData( GetClientData( line ) );
                event.SetString( GetString( line ) );
                event.SetInt( line );

                GetEventHandler()->ProcessEvent(event);
            }
        }
    }
}

#endif // !TARGET_API_MAC_OSX

#endif
