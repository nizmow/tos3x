/* maschinen und tos id */
hadesid		equ $68616465 /* 'hade' */

sweite		equ  $20000			    /* schrittweite ramtest */
mtadr1		equ  $8000000			/* doppelseitig */
mtadr2		equ  $2000000			/* 4mx32 */
mtadr3		equ  $400000            /* 1mx32 */
mem_set_adr	equ  $70000000

		/* special hades initialisation */
        reset                  /* reset all hardware */
		move.l  #$00FFC040,d0  /* no cache serialized */
		D0_DTT1
		D0_ITT1
		D0_DTT0
		D0_ITT0
		clr.l d0		/* all caches off */
        D0_CACR
        CINVA_BC
        D0_VBR           /* initialise VBR to zero */
        move.l  #$00000210,d0
        D0_TC            /* set no cache, precise for mc68060 (also works for mc68040) */
        lea.l   mem_set_adr,a0 /* set addresses */
        lea.l   $08000000,a1 /* mtadr1: doppelseitig */
        lea.l   $02000000,a2 /* mtadr2: 4mx32 */
        lea.l   $00400000,a3 /* mtadr3: */
        move.l  #hadesid,d3		/* test pattern */
        move.l  #-hadesid,d4	/* test pattern */
        clr.b   (a0)		/* default maximum */
        clr.l   d6			/* default 32mx32 module */
        clr.l   (4).w
        clr.l   (a1)
        clr.l   (a2)
        clr.l   (a3)
        clr.b   mem_set_adr+$800000
        clr.l   (a1)
        clr.l   (a2)
        clr.l   (a3)
        nop
        nop
        move.l  d3,(0).w 	/* start mit testmuster -> spiegelung eruieren */
        nop
        nop
		cmp.l   (a2),d3
		beq.s   non32mx32
		tst.l   (a2)
		beq.s   hades3
non32mx32:
		addq.w  #2,d6
		cmp.l   (a3),d3
		beq.s   non4mx32
		tst.l   (a3)
		beq.s   hades3
non4mx32:
		addq.w  #2,d6
hades3:
		clr.b   (a0)
		nop
		nop
		move.l  d3,(a1)		/* zweiseitig */
		move.l  d3,(4).w	/* zweiseitig modul 2 */
		nop
		cmp.l   (a1),d3
		beq.s   not_zweiseitig
		addq.w  #1,d6
not_zweiseitig:
		cmp.l   (4).w,d3
		beq.s   zweiseitig
		moveq.l #9,d6		/* nur ein modul einseitig */
		bra.s   mem_set_end
zweiseitig:
		cmpi.w  #2,d6
		bgt.s   mem_set_end
		beq.s   mem_set_fertig
		tst.w   d6
		bne.s   mem_set_end
		cmp.l   (a2),d3
		bne.s   mem_set_end
		moveq.l #9,d6
		bra.s   mem_set_end
mem_set_fertig:
		cmp.l   $00800000,d3
		bne.s   mem_set_end
		moveq.l #11,d6
mem_set_end:
		move.l  d6,d0
		swap    d0
		lsl.l   #4,d0
		adda.l  d0,a0
		clr.b   (a0)

        data
zero:
	    dc.l 0
		text

/* =========================================================================== */
/* ==== memconf for Hades ==================================================== */
/* =========================================================================== */

        lea       memcret(pc),a6
        bra       memchk
memcret:
        bne.s      noreset

resetvec:
        cmpi.l   #$31415926,(resvalid).w  /* Jump to resetvector? */
        bne.s    noreset                /* No --> noreset */
        move.l   (resvector).w,d0       /* Yes: old resvec to d0 */
        btst     #0,d0                  /* Address odd ? */
        bne.s    noreset                /* Yes --> noreset */
        movea.l  d0,a0                  /* resvec */
        lea      resetvec(pc),a6        /* save return address */
/* Note: the return address intentionally points to the resvalid test. */
/* So the reset routine must explicitly clear resvalid before returning */
/* to a6, otherwise there will be an infinite loop. */
        jmp      (a0)                   /* jump to resvec */
noreset:
        lea       memcret2(pc),a6               /* load return address */
        bra       memchk                        /* check if the memory configuration is valid */
memcret2:
        beq       nomemchk

		lea.l   (SUPSIZ*2+_supstk).w,a7  /* stack init */
		move.l  #hadesid,d3              /* bit pattern */
		move.l  #-hadesid,d4
		clr.l   (_shell_p).w
		move.l  #idinerr,(_buserror).w
		move.l  #sweite,d7               /* startadresse und schrittweite */
		movea.l d7,a0                    /* startadresse setzen */
		movea.l a0,a1
		nop     
		cmpi.l  #idinerr,(_buserror).w
		bne.s   tt_ramsize_done
idin:
		move.l  d3,-4(a1)
		move.l  d4,-8(a1)
		adda.l  d7,a1
		bra.s   idin
idinerr:
		move.l  #tt_ramsize_done,(_buserror).w
zonecheck:
		movea.l a0,a1			/* test auf spiegelung. wenn nicht da dann spiegelung */
		cmp.l   -4(a1),d3       
		bne.s   tt_ramsize_done
		cmp.l   -8(a1),d4
		bne.s   tt_ramsize_done
		move.l  d0,d2			/* 0->d2 */
		moveq.l #21,d1			/* loop counter */
store_mem:
		move.l  d2,-(a1)		/* write bit pattern */
		add.l   d3,d2			/* change pattern */
		dbf     d1,store_mem	/* next */
		movea.l a0,a1
		moveq.l #21,d1			/* loop counter */
check_mem:
		cmp.l   -(a1),d0		/* compare pattern */
		bne.s   tt_ramsize_done	/* not equal -> done */
		add.l   d3,d0
		dbf     d1,check_mem
		adda.l  d7,a0			/* next 128KB */
		bra.s   zonecheck
tt_ramsize_done:
		suba.l  d7,a0
		move.l  a0,d4
		lea.l   256,a0
		moveq.l #0,d0
		moveq.l #0,d1
		moveq.l #0,d2
		moveq.l #0,d3
clrmem:
		movem.l d0-d3,0(a0)
		movem.l d0-d3,16(a0)
		movem.l d0-d3,32(a0)
		movem.l d0-d3,48(a0)
		movem.l d0-d3,64(a0)
		movem.l d0-d3,80(a0)
		movem.l d0-d3,96(a0)
		movem.l d0-d3,112(a0)
		adda.l  #128,a0
		cmpa.l  #$00400000,a0
		blt.s   clrmem
		move.b  d6,(memctrl).w             /* set copy of hw memory config */
		move.l  d4,(_phystop).w            /* highest address as phystop */
		clr.l   (_ramtop).w				   /* no TT-RAM */

        move.l    #$752019F3,(_memvalid).w /* set memvalid to ok */
        move.l    #$237698AA,(_memval2).w  /* set memval2 to ok */
        move.l    #$5555AAAA,(_memval3).w  /* set memval3 to ok */
        move.l    #$1357BD13,(_ramvalid).w   /* ramtop is valid (ramvalid == RAMMAGIC) */

nomemchk:

		lea.l   (SUPSIZ*2+_supstk),a7  		/* reset supervisor stack */

/* clear the remainder of the BSS section */

        lea       (_has_dmasound).w,a0
        lea       BIOS_BSS_END,a1
clrbss:
        clr.w     (a0)+
        cmpa.l    a0,a1
        bne.s     clrbss

		move.l     #$ABCDEF42,d0
		lea.l      hadret1(pc),a6
		jmp        pcicheck
hadret1:
		move.l     a0,d0
		bne.s      hadret2
		lea.l      hadret2(pc),a6
		jmp        screen_init		/* screen karte initialisieren */
hadret2: ds.b 0

/* clear screen memory */
#if hades_vidmo == 2
scrsize equ ((640*400)/8)
#else
scrsize equ ((1280*960)/8)
#endif
        move.w     #(scrsize/16)-1,d1
        move.l     a0,(_v_bas_ad).w
        movea.l    a0,a1
clrscr:
        clr.l      (a0)+
        clr.l      (a0)+
        clr.l      (a0)+
        clr.l      (a0)+
        dbf        d1,clrscr

		lea.l      hadret3(pc),a6
		jmp        check_hardware
hadret3:
		move.b     #$0A,ldor /* floppy reset */
		
        lea.l     (psgsel).w,a0
        move.b    #$07,(a0)  /* select mixer control */
        move.b    #$C0,2(a0) /* Port A+B = output */
        move.b    #$0E,(a0)  /* select Port A */
        move.b    #7,2(a0) /* deselect floppy drives */

		move.b     #$0e,ldor /* floppy normal int activ */
		clr.b      fd_desel.l
		clr.b      (dma_sctr2).l  /* vme int off, scsi count0/eop und buserror off */
		move.l     _os_entry,(0).w
		move.l     reseth,(4).w

		bra.s      hadret4

		RESERVE_SPACE(_main,$e00030,$e002c8)

hadret4: ds.b 0

		/* end special hades initialisation */
