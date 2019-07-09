//
//  learnmenu.c
//  Pal
//
//  Created by Kirk Young on 7/7/19.
//

#include "main.h"

static int     g_iNumSelection = 0;
static int     g_iCurNewMagicMenuItem = 0;
WORD PALX_NewMagicMenuUpdate(void)
{
    return 0xFFFF;
}

VOID PALX_NewMagicMenuInit(WORD wItemFlags)
{
}

WORD PALX_NewMagicMenu(LPITEMCHANGED_CALLBACK lpfnMenuItemChanged, WORD wItemFlags)
{
    return 0;
}
