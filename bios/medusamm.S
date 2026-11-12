/* neuer ramtest */

medusa_stram_start   equ $7f000000      /* orginal st ram startadresse */

#if TOSVERSION >= 0x300
        bra.s medusa_cont
		dcb.b 40,-1

#else

        btst      #0,_os_conf+1             /* check bit: configured for 50hz? */
        beq.s     notpal                    /* (nope -- we're good ol' NTSC) */
        lea       ret_1b(pc),a6
        bra       waitvbl                   /* a short delay for PAL */
ret_1b:
#if TP_02 /* COLOR_60HZ */
        move.b    #0,(v_syncmod).w          /* yes -- twiddle to 60hz */
#else
        move.b    #2,(v_syncmod).w          /* yes -- twiddle to 50hz */
#endif
notpal:
/*
 * next, set up the palette(s)
 */

        lea.l     (palette).w,a1
        move.w    #16-1,d0
        lea.l     dflt_pal(pc),a0
initpal:
        move.w    (a0)+,(a1)+
        dbf       d0,initpal

/* set Video screen memory position to 0x10000 */
        move.b    #$01,(v_bas_h).w
        clr.b     (v_bas_m).w

#endif

medusa_cont:
        move.b    (memctrl).w,d6                /* d6 = memory controller configuration */
#if TOSVERSION < 0x300
        move.b    d6,(memconf).w                /* setup memory controller configuration register */
#endif

        move.l    (_phystop).w,d5               /* d5 -> (possible) top of physical mem */

        lea       memcret2(pc),a6               /* load return address */
        bra       memchk                        /* check if the memory configuration is valid */
memcret2:
        beq       nomemchk

#if TOSVERSION >= 0x300

domemchk:
        lea       (SUPSIZ*2+_supstk).w,a7       /* stack startup */
        move.l    #st_ramsize_done,_buserror.w     /* bus error means end of ram */
        move.w    #$FB55,d3           /* d3.w = difference between adjacent stored values */
        moveq     #2,d7
        swap      d7                  /* d7=$20000 */
        movea.l   d7,a0               /* a0 = address of current test zone */
next_zone:
        movea.l   a0,a1               /* a1 -> memory being tested */
        move.w    d0,d2               /* d2.w = test value */
        moveq.l   #42,d1              /* d1.w = loop count-1 */
store_mem:
        move.w    d2,-(a1)            /* store a value */
        add.w     d3,d2               /* update the value for next time */
        dbf       d1,store_mem        /* rinse & repeat */
/* now check the values we stored */
        movea.l   a0,a1               /* a1 -> test area */
        moveq.l   #42,d1              /* loop count */
check_mem:
        cmp.w     -(a1),d0
        bne.s     st_ramsize_done     /* miscompare, ram invalid, exit */
        add.w     d3,d0               /* update for next compare */
        dbf       d1,check_mem        /* until we're done */
        adda.l    d7,a0               /* point to next test area */
        cmp.l     #$820000,a0         /* nicht mehr als 8 MB +128 KB(wird wieder subtrahiert) */
        blt.s     next_zone

#else

domemchk:
                moveq #0,d6
                move.b #$a,(memconf).w          /* config auf 4 MB */
                lea medusa_stram_start+8,a0     /* beginn bank 1 */
                moveq #$20,d3
                swap d3                         /* d3=$200000 */
                moveq #0,d0
                move.w #$100-1,d1               /* $100 umlaeufe */
chkpatloop:
                move.w d0,(a0)+                 /* bank 1 */
                move.w d0,-2(a0,d3.l)           /* bank 2 */
                addi.w #$fa54,d0
                dbf d1,chkpatloop               /* next */
                blt chkpatloop
                lea v_bas_l.w,a0                /* low byt screen bei STe */
                moveq #90,d1                    /* test byt */
                move.b d1,(a0)                  /* byt einschreiben */
                nop
                moveq  #$20,d7                  /* d7 fuer normal ST vorbesetzen */
                lsl.l #4,d7                     /* d7 = $200 */
                cmp.b (a0),d1                   /* noch da? */
                bne.s chkmem1                   /* nein->kein STe */
                clr.b (a0)
                nop
                tst.b (a0)                      /* noch 0? */
                bne.s chkmem1                   /* nein->kein STe */
                moveq #4,d7                     /* STe anderer d7 wert */
                swap d7                         /* =$40000 */
chkmem1:
                move.l #medusa_stram_start+$200000,d1  /* beginn test Bank 2 */
                move.l #medusa_stram_start/$10000+4,d5  /* ende "ST Ram" default (7f040000(7f000000+2*128k default))/10000 */
                moveq #1,d4                     /* 2 umlaeufe */
chkmemloop:
                lsr.w #2,d6
                move.l d7,a0
                addq.l #8,a0                    /* $208 */
                lea chkmem3(pc),a4              /* ruecksprungadresse */
                bra memchk0                     /* testen */
chkmem3:
                beq.s chkmem7                   /* ok -> 128 KB */
                move.l d7,a0
                add.l d7,a0
                addq.l #8,a0                    /* $408 */
                lea chkmem4(pc),a4              /* ruecksprungadresse */
                addq.w #6,d5                    /* +512-128kb/10000 */
                bra memchk0                     /* testen */
chkmem4:
                beq.s chkmem6                   /* ok -> 512 KB */
                lea _buserror.w,a0              /* $8 */
                lea chkmem5(pc),a4              /* ruecksprungadresse */
                subq.w #8,d5                    /* -512kb/10000 */
                bra memchk0                     /* testen */
chkmem5:
                bne.s chkmem7                   /* -> nichts in dieser Bank */
                addi.w #$20,d5                  /* +2mb/10000 */
                addq.w #4,d6
chkmem6:
                addq.w #4,d6
chkmem7:
                sub.l d3,d1
                dbf d4,chkmemloop               /* next */

                swap d5                         /* *$10000 */
                move.b d6,memconf.w
                lea $6000.w,a7                  /* stack init */
                move.l #st_ramsize_done,_buserror.w       /* neuer buserrorvektor */
                move.w #$fb55,d3                /* bitmuster */
                moveq #2,d7                     /* startadresse und schrittweite */
                swap d7                         /* =$20000 */
                move.l d7,a0                    /* startadresse setzen */
next_zone:
                move.l a0,a1
                move.w d0,d2                    /* 0->d2 */
                moveq #$2a,d1                   /* schleifenindex */
store_mem:
                move.w d2,-(a1)                 /* bitmuster einschreiben */
                add.w d3,d2                     /* bitmuster veraendern */
                dbf d1,store_mem                /* next */
                move.l a0,a1
                moveq #42,d1                    /* schleifenindex */
check_mem:
                cmp.w -(a1),d0                  /* bitmuster vergleichen */
                bne.s st_ramsize_done           /* ungleich -> weg + fertig */
                add.w d3,d0
                dbf d1,check_mem
                add.l d7,a0                     /* naechster 128 KB */
                cmp.l #$A20000,a0               /* nicht mehr als 10 MB +128 KB(wird wieder subtrahiert) */
                blt next_zone
#endif

st_ramsize_done:
                sub.l d7,a0                     /* endadresse speicher fast ram 1 */
                move.l a0,d4

/* =========================================================================== */
/* ==== This part is executed only on first boot ============================= */
/* =========================================================================== */

        /* Clear the memory */
#if TP_04 & !TP_03 /* MEM_INIT & !RAMRESET */
		        movea.w   #$100,a0
#else
        		lea       sysvars_start,a0      /* beginn loeschen */
#endif
                moveq #0,d0

clrmem:
                move.l d0,(a0)+                 /* speicher loeschen */
                move.l d0,(a0)+
                move.l d0,(a0)+
                move.l d0,(a0)+
                move.l d0,(a0)+
                move.l d0,(a0)+
                move.l d0,(a0)+
                move.l d0,(a0)+
                cmp.l d4,a0                     /* schon fertig */
                blt.s clrmem                    /* nein -> wiederholen */
                move.b d6,memctrl.w             /* config sichern */
#if TOSVERSION < 0x300
                move.l d5,____md.w              /* st ram top */
#endif
                move.l d4,_phystop.w            /* memtop sichern */
                clr.l _ramtop.w                 /* kein TT Ram */
                move.l #$752019f3,_memvalid.w   /* memvalidwerte */
                move.l #$237698aa,_memval2.w
                move.l #$5555aaaa,_memval3.w
                move.l #$1357bd13,_ramvalid.w

nomemchk:

#if (TOSVERSION >= 0x300)
                lea (SUPSIZ*2+_supstk).l,a7     /* stack startup */
                lea _has_dmasound.w,a0
                lea BIOS_BSS_END,a1
                moveq #0,d0
clrbss:
                move.w     d0,(a0)+
                cmpa.l     a0,a1
                bne.s      clrbss

				jsr screen_init
                moveq #0,d0

scrsize equ 524288
                move.w #(scrsize/16)-1,d1
                lea        medusa_stram_start,a0
                move.l     a0,_v_bas_ad.w       /* screen adr setzen */

#else
                lea (SUPSIZ*2+_supstk).w,a7     /* stack startup */
                lea _has_dmasound.w,a2
                clr.b (a2)+
                move.l a7,a6                    /* stack sichern */
                move.l #nodmasound,_buserror.w  /* buserrorvektor setzen */
                clr.w sndmactl.w                /* dma sound? */
                st -1(a2)                       /* ja setzen */
                lea microwtab(pc),a0            /* wertetabelle */
                move.w (a0)+,mwmask.w
                bra.s checkmicro
microwtab:
        dc.w      $0ffe  /* value for microwire mask register */
        dc.w      $09d1                     /* 10-011-101000-1 = LCM - Master Volume - 0 db volume (max) - end-bit */
        dc.w      $0aa9                     /* 10-101-010100-1 = LCM - Left channel volume - 0 db volume (max) - end-bit */
        dc.w      $0a29                     /* 10-100-010100-1 = LCM - Right channel volume - 0 db volume (max) - end-bit */
        dc.w      $090d                     /* 10-010-000110-1 = LCM - Trebble control - 0 db (linear) - end-bit */
        dc.w      $088d                     /* 10-001-000110-1 = LCM - Bass control - 0 db (linear) - end-bit */
        dc.w      $0803                     /* 10-000-000001-1 = LCM - Mixer - DMA + YM2149 - end-bit */
        dc.w      0
nextmicro:
                move.w d0,mwdata.w
waitmicro:
                tst.w mwdata.w
                bne.s waitmicro
checkmicro:
                move.w (a0)+,d0                 /* naechster wert */
                bne.s nextmicro                 /* wiederholen bis null */
nodmasound:
                move.l a6,a7                    /* stack restaurieren */
                lea v_bas_l.w,a6                /* adresse low byt screen */
                moveq #90,d0                    /* test byt */
                move.b d0,(a6)                  /* low byt screen setzen */
                nop
                cmp.b (a6),d0                   /* noch gleich? */
                bne.s nostedetect               /* nein -> */
                clr.b (a6)                      /* low byt loeschen */
                nop
                tst.b (a6)                      /* noch 0? */
nostedetect:
                sne (a2)+                       /* STEFlag mode byt setzen (STE -> =0) */
#if BINEXACT
                /* ((__ebss-__sbss+15)/16)-1 */
                move.w #$c2a,d1                 /* a04-ccb4 loeschen */
#else
                move.l #BIOS_BSS_END+15,d1
                sub.l  #__sbss,d1
                lsr.l  #4,d1
                subq.w #1,d1
#endif
                moveq #0,d0
clrbss:
                move.l d0,(a2)+                 /* tos bereich loeschen */
                move.l d0,(a2)+
                move.l d0,(a2)+
                move.l d0,(a2)+
                dbf d1,clrbss

scrsize equ ((640*400)/8+$300)

                move.w #(scrsize/16)-1,d1
                move.l ____md.w,a0              /* st top */
                lea -scrsize(a0),a0             /* -screen laenge */
                move.l a0,_v_bas_ad.w           /* screen adr setzen */
                move.b (_v_bas_ad+1).w,v_bas_h.w  /* screen setzen */
                move.b (_v_bas_ad+2).w,v_bas_m.w

#endif

clrscr:
                move.l d0,(a0)+                 /* screen loeschen */
                move.l d0,(a0)+
                move.l d0,(a0)+
                move.l d0,(a0)+
                dbf d1,clrscr
#if BINEXACT
#if TOSVERSION >= 0x300
                bra   gemchk                    /* ende e002c8 */
                RESERVE_SPACE(domemchk,$e00110,$e002c8)
#else
                bra.s gemchk                    /* ende e002b2 */
                RESERVE_SPACE(domemchk,$e000e2,$e002b2)
#endif
#endif

