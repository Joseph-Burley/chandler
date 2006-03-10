/////////////////////////////////////////////////////////////////////////////
// Name:        popupwin.h
// Purpose:
// Author:      Robert Roebling
// Created:
// Id:          $Id: popupwin.h,v 1.13 2006/02/27 09:16:28 RR Exp $
// Copyright:   (c) 2001 Robert Roebling
// Licence:     wxWindows licence
/////////////////////////////////////////////////////////////////////////////

#ifndef __GTKPOPUPWINH__
#define __GTKPOPUPWINH__

#include "wx/defs.h"
#include "wx/panel.h"
#include "wx/icon.h"

//-----------------------------------------------------------------------------
// wxPopUpWindow
//-----------------------------------------------------------------------------

class WXDLLIMPEXP_CORE wxPopupWindow: public wxPopupWindowBase
{
public:
    wxPopupWindow() { }
    virtual ~wxPopupWindow();

    wxPopupWindow(wxWindow *parent, int flags = wxBORDER_NONE)
        { (void)Create(parent, flags); }
    bool Create(wxWindow *parent, int flags = wxBORDER_NONE);

    virtual bool Show( bool show = TRUE );

    // implementation
    // --------------

    virtual void OnInternalIdle();
    
    // GTK time when connecting to button_press signal
    wxUint32  m_time;


protected:
    void GtkOnSize( int x, int y, int width, int height );

    virtual void DoSetSize(int x, int y,
                           int width, int height,
                           int sizeFlags = wxSIZE_AUTO);

    virtual void DoMoveWindow(int x, int y, int width, int height);

private:
    DECLARE_EVENT_TABLE()
    DECLARE_DYNAMIC_CLASS(wxPopupWindow)
};

#endif // __GTKPOPUPWINDOWH__
