//
//  learnmenu.h
//  Pal
//
//  Created by Kirk Young on 7/7/19.
//

#ifndef learnmenu_h
#define learnmenu_h

#ifdef __cplusplus
extern "C"
{
#endif
    
    WORD PALX_NewMagicMenuUpdate(void);
    
    VOID PALX_NewMagicMenuInit(WORD wItemFlags);
    
    WORD PALX_NewMagicMenu(LPITEMCHANGED_CALLBACK lpfnMenuItemChanged, WORD wItemFlags);
    
#ifdef __cplusplus
}
#endif
#endif /* learnmenu_h */
